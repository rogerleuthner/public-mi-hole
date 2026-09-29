# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

"""Asynchronous DNS filtering server."""

import socket
import time

import uasyncio
from config import (
    DATABASE,
    DATABASE_CACHE_SIZE,
    DNS_PORT,
    STATIC_IP,
)
from dns_database.dnsd import DNSDatabase
from dns_stats import DNSStats
from machine import Pin
import neopixel
import asyncio

BUFFER_SIZE = 1536
TIMEOUT_MS = 2000
UPSTREAM_IP = "1.1.1.1"
UPSTREAM_PORT = DNS_PORT


class DNSServer:
    """Async DNS filtering and forwarding server."""

    def __init__(
        self,
        database,
        stats,
        listen_ip=STATIC_IP.ip,
        port=DNS_PORT,
        upstream_ip=UPSTREAM_IP,
        upstream_port=UPSTREAM_PORT,
        timeout_ms=TIMEOUT_MS,
    ):
        self.db = database
        self.stats = stats

        self.listen_ip = listen_ip
        self.port = port
        self.upstream = (
            upstream_ip,
            upstream_port,
        )
        self.timeout_ms = timeout_ms

        self.server = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        self.server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        self.server.bind(
            (
                listen_ip,
                port,
            )
        )

        self.server.setblocking(False)

        self.upstream_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        self.upstream_socket.setblocking(False)

        self.pending = {}

        self.next_transaction_id = 1

        self.receiver_task = None
        self.cleanup_task = None
        
        self.led = neopixel.NeoPixel(Pin(48), 1)

    # ================================================================
    # DNS parsing
    # ================================================================

    def _question_end(self, packet, length):
        pos = 12

        while True:
            if pos >= length:
                return -1

            label_length = packet[pos]

            if label_length < 0xC0:
                if label_length == 0:
                    pos += 1

                    if pos + 4 > length:
                        return -1

                    return pos + 4

                pos += label_length + 1

                if pos > length:
                    return -1

            else:
                if pos + 2 > length:
                    return -1

                pos += 2

                if pos + 4 > length:
                    return -1

                return pos + 4

    def _read_qname(self, packet, length):
        pos = 12
        labels = []

        while pos < length:
            label_length = packet[pos]
            pos += 1

            if label_length == 0:
                return ".".join(labels)

            # Compression pointers are not expected in the question
            # section, but reject them rather than attempting to follow
            # arbitrary pointers.
            if label_length >= 0xC0:
                return None

            if label_length > 63:
                return None

            if pos + label_length > length:
                return None

            label = packet[
                pos : pos + label_length
            ]

            try:
                labels.append(
                    label.decode("ascii").lower()
                )
            except UnicodeError:
                return None

            pos += label_length

        return None

    # ================================================================
    # Responses
    # ================================================================

    def _blocked_response(self, packet, length):
        if length < 12:
            return None

        txbuf = bytearray(length)
        txbuf[:length] = packet[:length]

        flags = (
            (packet[2] << 8)
            | packet[3]
        )

        flags |= 0x8000
        flags |= 0x0080
        flags &= 0xFFF0
        flags |= 0x0003

        txbuf[2] = (
            flags >> 8
        ) & 0xFF

        txbuf[3] = flags & 0xFF

        for index in range(6, 12):
            txbuf[index] = 0

        return txbuf

    # ================================================================
    # Transaction IDs
    # ================================================================

    def _allocate_transaction_id(self):
        for _ in range(65535):
            transaction_id = (
                self.next_transaction_id
            )

            self.next_transaction_id += 1

            if self.next_transaction_id > 65535:
                self.next_transaction_id = 1

            if transaction_id not in self.pending:
                return transaction_id

        return None

    # ================================================================
    # DNS request handling
    # ================================================================

    async def flash(self, color, duration_ms=1):
        self.led[0] = color
        self.led.write()
        await asyncio.sleep_ms(duration_ms)
        self.led[0] = (0,0,0)
        self.led.write()

    async def handle_request(
        self,
        packet,
        length,
        client,
    ):
        if length < 17:
            return

        qdcount = (
            (packet[4] << 8)
            | packet[5]
        )

        if qdcount != 1:
            return

        question_end = self._question_end(
            packet,
            length,
        )

        if question_end < 0:
            return

        domain = self._read_qname(
            packet,
            length,
        )

        if not domain:
            return

        blocked = self.db.contains_qname_or_parent(
            packet,
            12,
        )

        if blocked:
            asyncio.create_task(self.flash((255,0,0)))
        else:
            asyncio.create_task(self.flash((0,255,0)))

        activity_id = self.stats.record_query(
            domain,
            client[0],
            blocked,
        )

        if blocked:
            response = self._blocked_response(
                packet,
                length,
            )

            if response:
                try:
                    self.server.sendto(
                        response,
                        client,
                    )
                except OSError:
                    self.stats.record_error(
                        activity_id,
                    )

            return

        original_id = (
            (packet[0] << 8)
            | packet[1]
        )

        upstream_id = (
            self._allocate_transaction_id()
        )

        if upstream_id is None:
            self.stats.record_error(
                activity_id,
            )
            return

        upstream_packet = bytearray(
            packet[:length]
        )

        upstream_packet[0] = (
            upstream_id >> 8
        ) & 0xFF

        upstream_packet[1] = (
            upstream_id & 0xFF
        )

        self.pending[upstream_id] = (
            client,
            original_id,
            time.ticks_ms(),
            activity_id,
        )

        try:
            self.upstream_socket.sendto(
                upstream_packet,
                self.upstream,
            )

        except OSError:
            self.pending.pop(
                upstream_id,
                None,
            )

            self.stats.record_error(
                activity_id,
            )

    # ================================================================
    # Upstream response receiver
    # ================================================================

    async def _upstream_receiver(self):
        while True:
            try:
                response, _ = (
                    self.upstream_socket.recvfrom(
                        BUFFER_SIZE,
                    )
                )

                if len(response) < 2:
                    continue

                upstream_id = (
                    (response[0] << 8)
                    | response[1]
                )

                request = self.pending.pop(
                    upstream_id,
                    None,
                )

                if request is None:
                    continue

                (
                    client,
                    original_id,
                    timestamp,
                    activity_id,
                ) = request

                latency_ms = time.ticks_diff(
                    time.ticks_ms(),
                    timestamp,
                )

                response = bytearray(
                    response
                )

                response[0] = (
                    original_id >> 8
                ) & 0xFF

                response[1] = (
                    original_id & 0xFF
                )

                try:
                    self.server.sendto(
                        response,
                        client,
                    )
                except OSError:
                    self.stats.record_error(
                        activity_id,
                    )
                else:
                    self.stats.record_response(
                        activity_id,
                        latency_ms,
                    )

            except OSError:
                pass

            await uasyncio.sleep_ms(1)

    # ================================================================
    # Timeout cleanup
    # ================================================================

    async def _cleanup_pending(self):
        while True:
            now = time.ticks_ms()
            expired = []

            for transaction_id, request in (
                self.pending.items()
            ):
                _, _, timestamp, activity_id = request

                if (
                    time.ticks_diff(
                        now,
                        timestamp,
                    )
                    >= self.timeout_ms
                ):
                    expired.append(
                        (
                            transaction_id,
                            activity_id,
                        )
                    )

            for (
                transaction_id,
                activity_id,
            ) in expired:
                self.pending.pop(
                    transaction_id,
                    None,
                )

                self.stats.record_timeout(
                    activity_id,
                )

            await uasyncio.sleep_ms(100)

    # ================================================================
    # Main server
    # ================================================================

    async def serve_forever(self):
        print(
            "DNS server listening asynchronously "
            f"on {self.listen_ip}:{self.port}"
        )

        print(
            "Upstream DNS: "
            f"{self.upstream[0]}:{self.upstream[1]}"
        )

        self.receiver_task = (
            uasyncio.create_task(
                self._upstream_receiver()
            )
        )

        self.cleanup_task = (
            uasyncio.create_task(
                self._cleanup_pending()
            )
        )

        while True:
            try:
                packet, client = self.server.recvfrom(BUFFER_SIZE)
                length = len(packet)
                uasyncio.create_task(self.handle_request(packet, length, client))
            except OSError:
                pass
            await uasyncio.sleep_ms(0)  # yield every iteration, not just on failure

    # ================================================================
    # Cleanup
    # ================================================================

    def close(self):
        if self.receiver_task is not None:
            try:
                self.receiver_task.cancel()
            except Exception:
                pass

        if self.cleanup_task is not None:
            try:
                self.cleanup_task.cancel()
            except Exception:
                pass

        try:
            self.upstream_socket.close()
        except OSError:
            pass

        try:
            self.server.close()
        except OSError:
            pass


def create_dns_server():
    """Create the database, telemetry object, and DNS server."""

    database = DNSDatabase(
        DATABASE,
        cache_size=DATABASE_CACHE_SIZE,
    )

    stats = DNSStats()

    server = DNSServer(
        database,
        stats,
    )

    return database, stats, server