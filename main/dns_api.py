# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

"""Small HTTP/JSON API for the Mi-Hole dashboard."""

import gc
import os
import sys
import time

import esp32
import machine
import network
import uasyncio
import ujson

HTTP_PORT = 80

MAX_REQUEST_LINE = 512
MAX_HEADERS = 2048

class DNSAPI:
    """Minimal HTTP API for Mi-Hole telemetry."""

    def __init__(
        self,
        dns_server,
        stats,       
        host="0.0.0.0",
        port=HTTP_PORT,
    ):
        self.dns_server = dns_server
        self.stats = stats

        self.host = host
        self.port = port

        self.server = None

        self._cpu_monitor = None

        self._http_requests_total = 0
        self._http_bytes_sent_total = 0
        self._rate_samples = {}

    # ============================================================
    # Lifecycle
    # ============================================================

    async def start(self):
        self.server = await uasyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )

        self._cpu_monitor = _CPULoadMonitor()
        uasyncio.create_task(
            self._cpu_monitor.run()
        )

        print(
            "HTTP API listening on "
            f"{self.host}:{self.port}"
        )

    async def close(self):
        if self._cpu_monitor is not None:
            self._cpu_monitor.stop()
            self._cpu_monitor = None

        if self.server is None:
            return

        try:
            self.server.close()
        except Exception:
            pass

        try:
            await self.server.wait_closed()
        except Exception:
            pass

        self.server = None

    # ============================================================
    # Request handling
    # ============================================================

    async def _handle_client(
        self,
        reader,
        writer,
    ):
        try:
            request_line = await reader.readline()

            if not request_line:
                return

            if len(request_line) > MAX_REQUEST_LINE:
                await self._send_json(
                    writer,
                    414,
                    {
                        "error": "request_too_long",
                    },
                )
                return

            try:
                method, target, _version = (
                    request_line.decode("ascii")
                    .strip()
                    .split(" ", 2)
                )
            except (
                ValueError,
                UnicodeError,
            ):
                await self._send_json(
                    writer,
                    400,
                    {
                        "error": "bad_request",
                    },
                )
                return

            header_bytes = 0

            while True:
                line = await reader.readline()

                if not line:
                    break

                header_bytes += len(line)

                if header_bytes > MAX_HEADERS:
                    await self._send_json(
                        writer,
                        431,
                        {
                            "error": "headers_too_large",
                        },
                    )
                    return

                if line in (
                    b"\r\n",
                    b"\n",
                ):
                    break

            if method == "OPTIONS":
                await self._send_empty(
                    writer,
                    204,
                )
                return

            path, query = self._split_target(
                target
            )

            # ----------------------------------------------------
            # Health
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/health"
            ):
                await self._send_json(
                    writer,
                    200,
                    {
                        "ok": True,
                    },
                )
                return

            # ----------------------------------------------------
            # Statistics
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/stats"
            ):
                await self._send_json(
                    writer,
                    200,
                    self.stats.snapshot(),
                )
                return

            # ----------------------------------------------------
            # Activity
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/activity"
            ):
                limit = self._query_int(
                    query,
                    "limit",
                    50,
                    1,
                    100,
                )

                await self._send_json(
                    writer,
                    200,
                    {
                        "items": self.stats.activity(
                            limit
                        ),
                    },
                )
                return

            # ----------------------------------------------------
            # Top blocked domains
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/domains"
            ):
                limit = self._query_int(
                    query,
                    "limit",
                    10,
                    1,
                    50,
                )

                await self._send_json(
                    writer,
                    200,
                    {
                        "items": self.stats.top_domains(
                            limit
                        ),
                    },
                )
                return

            # ----------------------------------------------------
            # Top clients
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/clients"
            ):
                limit = self._query_int(
                    query,
                    "limit",
                    10,
                    1,
                    50,
                )

                await self._send_json(
                    writer,
                    200,
                    {
                        "items": self.stats.top_clients(
                            limit
                        ),
                    },
                )
                return

            # ----------------------------------------------------
            # Configuration
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/config"
            ):
                await self._send_json(
                    writer,
                    200,
                    self._config_snapshot(),
                )
                return

            # ----------------------------------------------------
            # System information
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/system"
            ):
                await self._send_json(
                    writer,
                    200,
                    self._system_snapshot(),
                )
                return

            # ----------------------------------------------------
            # SBC hardware statistics
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/sbc"
            ):
                await self._send_json(
                    writer,
                    200,
                    self._sbc_snapshot(),
                )
                return

            # ----------------------------------------------------
            # Throughput
            # ----------------------------------------------------

            if (
                method == "GET"
                and path == "/api/throughput"
            ):
                await self._send_json(
                    writer,
                    200,
                    self._throughput_snapshot(),
                )
                return

            # ----------------------------------------------------
            # Reset statistics
            # ----------------------------------------------------

            if (
                method == "POST"
                and path == "/api/stats/reset"
            ):
                self.stats.reset()

                await self._send_json(
                    writer,
                    200,
                    {
                        "ok": True,
                    },
                )
                return

            await self._send_json(
                writer,
                404,
                {
                    "error": "not_found",
                },
            )

        except Exception as exc:
            print(
                "HTTP API error:",
                exc,
            )

            try:
                await self._send_json(
                    writer,
                    500,
                    {
                        "error": "internal_server_error",
                    },
                )
            except Exception:
                pass

        finally:
            try:
                writer.close()
            except Exception:
                pass

            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ============================================================
    # Snapshots
    # ============================================================

    def _config_snapshot(self):
        return {
            "listen_ip": self.dns_server.listen_ip,
            "dns_port": self.dns_server.port,
            "upstream_ip": self.dns_server.upstream[0],
            "upstream_port": self.dns_server.upstream[1],
            "timeout_ms": self.dns_server.timeout_ms,
        }

    def _system_snapshot(self):
        free_heap = None
        allocated_heap = None

        try:
            free_heap = gc.mem_free()
            allocated_heap = gc.mem_alloc()
        except Exception:
            pass

        wifi_connected = False
        wifi_rssi = None
        ip_address = None

        try:
            if hasattr(
                network.WLAN,
                "IF_STA",
            ):
                wlan = network.WLAN(
                    network.WLAN.IF_STA
                )
            else:
                wlan = network.WLAN(
                    network.STA_IF
                )

            wifi_connected = wlan.isconnected()

            if wifi_connected:
                try:
                    wifi_rssi = wlan.status(
                        "rssi"
                    )
                except Exception:
                    pass

                try:
                    ip_address = wlan.ifconfig()[0]
                except Exception:
                    pass

        except Exception:
            pass

        micropython_version = "unknown"

        try:
            version = (
                sys.implementation.version
            )

            micropython_version = ".".join(
                str(part)
                for part in version
            )
        except Exception:
            pass

        return {
            "uptime_ms": time.ticks_ms(),
            "free_heap": free_heap,
            "allocated_heap": allocated_heap,
            "wifi_connected": wifi_connected,
            "wifi_rssi": wifi_rssi,
            "ip_address": ip_address,
            "micropython": micropython_version,
            "pending_requests": len(
                self.dns_server.pending
            ),
        }

    def _sbc_snapshot(self):
        cpu_freq_hz = None

        try:
            cpu_freq_hz = machine.freq()
        except Exception:
            pass

        flash_total = None
        flash_used = None
        flash_free = None

        try:
            stat = os.statvfs("/")
            block_size = stat[0]
            total_blocks = stat[2]
            free_blocks = stat[3]

            flash_total = block_size * total_blocks
            flash_free = block_size * free_blocks
            flash_used = flash_total - flash_free
        except Exception:
            pass

        temperature_c = None

        try:
            # Newer firmware builds expose this for
            # the S3's on-die sensor.
            temperature_c = esp32.mcu_temperature()
        except Exception:
            try:
                # Fallback for ports that only expose the
                # legacy, uncalibrated Fahrenheit reading.
                temperature_c = (
                    (esp32.raw_temperature() - 32) * 5 / 9
                )
            except Exception:
                pass

        reset_cause = None

        try:
            reset_cause = self._reset_cause_name(
                machine.reset_cause()
            )
        except Exception:
            pass

        wifi_tx_power = None

        try:
            if hasattr(
                network.WLAN,
                "IF_STA",
            ):
                wlan = network.WLAN(
                    network.WLAN.IF_STA
                )
            else:
                wlan = network.WLAN(
                    network.STA_IF
                )

            wifi_tx_power = wlan.config(
                "txpower"
            )
        except Exception:
            pass

        return {
            "cpu_freq_mhz": (
                cpu_freq_hz // 1000000
                if cpu_freq_hz is not None
                else None
            ),
            "cpu_util_pct": (
                self._cpu_monitor.utilization_pct
                if self._cpu_monitor is not None
                else None
            ),
            "flash_total_bytes": flash_total,
            "flash_used_bytes": flash_used,
            "flash_free_bytes": flash_free,
            "temperature_c": (
                round(temperature_c, 1)
                if temperature_c is not None
                else None
            ),
            "reset_cause": reset_cause,
            "wifi_tx_power_dbm": wifi_tx_power,
        }

    def _throughput_snapshot(self):
        now = time.ticks_ms()

        dns_queries = None

        try:
            dns_queries = self.stats.snapshot().get(
                "queries"
            )
        except Exception:
            pass

        return {
            "dns_queries_total": dns_queries,
            "dns_queries_per_sec": self._rate_since(
                "dns_queries",
                dns_queries,
                now,
            ),
            "http_requests_total": self._http_requests_total,
            "http_requests_per_sec": self._rate_since(
                "http_requests",
                self._http_requests_total,
                now,
            ),
            "http_bytes_sent_total": self._http_bytes_sent_total,
            "http_bytes_sent_per_sec": self._rate_since(
                "http_bytes",
                self._http_bytes_sent_total,
                now,
            ),
        }

    def _rate_since(
        self,
        key,
        value,
        now_ms,
    ):
        if value is None:
            return None

        previous = self._rate_samples.get(key)
        self._rate_samples[key] = (
            value,
            now_ms,
        )

        if previous is None:
            return None

        previous_value, previous_ms = previous
        elapsed_ms = time.ticks_diff(
            now_ms,
            previous_ms,
        )

        if elapsed_ms <= 0:
            return None

        delta = value - previous_value

        if delta < 0:
            # Counter went backwards (e.g. stats were reset).
            return None

        return round(
            delta / (elapsed_ms / 1000),
            2,
        )

    @staticmethod
    def _reset_cause_name(cause):
        names = {
            machine.PWRON_RESET: "power_on",
            machine.HARD_RESET: "hard",
            machine.WDT_RESET: "watchdog",
            machine.DEEPSLEEP_RESET: "deep_sleep",
            machine.SOFT_RESET: "soft",
        }

        return names.get(
            cause,
            "unknown",
        )

    # ============================================================
    # HTTP helpers
    # ============================================================

    async def _send_json(
        self,
        writer,
        status,
        payload,
    ):
        body = ujson.dumps(
            payload
        ).encode("utf-8")

        reason = self._status_reason(
            status
        )

        headers = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            "Connection: close\r\n"
            "\r\n"
        )

        writer.write(
            headers.encode("ascii")
        )

        writer.write(body)

        await writer.drain()

        self._http_requests_total += 1
        self._http_bytes_sent_total += len(
            headers
        ) + len(body)

    async def _send_empty(
        self,
        writer,
        status,
    ):
        reason = self._status_reason(
            status
        )

        headers = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n"
            "\r\n"
        )

        writer.write(
            headers.encode("ascii")
        )

        await writer.drain()

        self._http_requests_total += 1
        self._http_bytes_sent_total += len(
            headers
        )

    @staticmethod
    def _status_reason(status):
        reasons = {
            200: "OK",
            204: "No Content",
            400: "Bad Request",
            404: "Not Found",
            414: "URI Too Long",
            431: "Request Header Fields Too Large",
            500: "Internal Server Error",
        }

        return reasons.get(
            status,
            "Error",
        )

    # ============================================================
    # Query parsing
    # ============================================================

    @staticmethod
    def _split_target(target):
        if "?" not in target:
            return target, {}

        path, query_string = target.split(
            "?",
            1,
        )

        query = {}

        for item in query_string.split("&"):
            if "=" not in item:
                continue

            key, value = item.split(
                "=",
                1,
            )

            query[key] = value

        return path, query

    @staticmethod
    def _query_int(
        query,
        key,
        default,
        minimum,
        maximum,
    ):
        value = query.get(key)

        if value is None:
            return default

        try:
            value = int(value)
        except ValueError:
            return default

        return max(
            minimum,
            min(maximum, value),
        )


class _CPULoadMonitor:
    """Estimate MicroPython event-loop load from scheduling latency."""

    SAMPLE_MS = 1000
    TICK_MS = 10

    def __init__(self):
        self.utilization_pct = 0.0
        self._running = True

    async def run(self):
        while self._running:
            window_start = time.ticks_ms()
            total_lateness = 0
            samples = 0

            while (
                time.ticks_diff(
                    time.ticks_ms(),
                    window_start,
                )
                < self.SAMPLE_MS
            ):
                start = time.ticks_ms()

                await uasyncio.sleep_ms(
                    self.TICK_MS
                )

                elapsed = time.ticks_diff(
                    time.ticks_ms(),
                    start,
                )

                lateness = max(
                    0,
                    elapsed - self.TICK_MS,
                )

                total_lateness += lateness
                samples += 1

            if samples:
                average_lateness = (
                    total_lateness / samples
                )

                self.utilization_pct = round(
                    min(
                        100.0,
                        (
                            average_lateness
                            / self.TICK_MS
                        ),
                    ),
                    1,
                )

    def stop(self):
        self._running = False

    

# class _CPULoadMonitor:
#     """Rough CPU utilization estimate for a cooperatively-scheduled
#     MicroPython event loop.

#     There is no OS-level scheduler to query on bare-metal
#     MicroPython, so this approximates load by comparing how many
#     no-op yields a dedicated background task can complete in a
#     fixed window against a baseline captured once at startup, when
#     the loop is otherwise idle. A busier loop starves this task of
#     turns, so fewer yields per window implies higher utilization.
#     """

#     SAMPLE_MS = 200
#     CALIBRATION_MS = 1000

#     def __init__(self):
#         self.utilization_pct = 0.0

#         self._baseline = None
#         self._running = True

#     async def run(self):
#         self._baseline = await self._count_yields(
#             self.CALIBRATION_MS
#         )

#         if self._baseline <= 0:
#             self._baseline = 1

#         while self._running:
#             count = await self._count_yields(
#                 self.SAMPLE_MS
#             )

#             expected = self._baseline * (
#                 self.SAMPLE_MS / self.CALIBRATION_MS
#             )

#             if expected <= 0:
#                 expected = 1

#             busy_fraction = 1.0 - min(
#                 1.0,
#                 count / expected,
#             )

#             self.utilization_pct = round(
#                 max(0.0, busy_fraction) * 100,
#                 1,
#             )

#             print(
#                 "baseline =", self._baseline,
#                 "count =", count,
#                 "expected =", expected,
#             )

#     async def _count_yields(self, duration_ms):
#         start = time.ticks_ms()
#         count = 0

#         while (
#             time.ticks_diff(time.ticks_ms(), start)
#             < duration_ms
#         ):
#             await uasyncio.sleep_ms(0)
#             count += 1

#         return count

#     def stop(self):
#         self._running = False
