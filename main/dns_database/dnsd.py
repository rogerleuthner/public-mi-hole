# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

"""
DNSD v4 runtime for MicroPython 1.29 / ESP32-S3.

Designed for high-rate DNS filtering.

Features
========

* No mmap.
* No pathlib.
* No argparse.
* No IDNA dependency.
* No conversion of DNS packets to strings.
* Direct DNS wire-format QNAME lookup.
* Case-insensitive DNS matching.
* FNV-1a label index.
* Binary-search label lookup.
* Binary-search DAFSA transitions.
* Reusable I/O buffers.
* Reusable QNAME offset arrays.
* DNS compression-pointer support.
* Bounded label cache.
"""

import struct
from array import array

# micropy compatibility
try:
    from micropython import const # type: ignore
except ImportError:
    def const(value):
        return value

# micropy compatibility
class Struct:
    def __init__(self, fmt):
        self.format = fmt
        self.size = struct.calcsize(fmt)

    def pack(self, *args):
        return struct.pack(self.format, *args)

    def unpack(self, data):
        return struct.unpack(self.format, data)

    def pack_into(self, buf, offset, *args):
        return struct.pack_into(self.format, buf, offset, *args)

    def unpack_from(self, data, offset=0):
        return struct.unpack_from(self.format, data, offset)


# ============================================================
# Constants
# ============================================================

_MAGIC = b"DNSD"

_VERSION = const(4)

_HEADER_SIZE = const(26)

_MAX_LABEL = const(63)

_MAX_NAME_LABELS = const(127)

_MAX_NAME_WIRE = const(255)

_FNV_OFFSET = const(2166136261)

_FNV_PRIME = const(16777619)

_HEADER = Struct("<4sBBIIIII")

_LABEL_INDEX = Struct("<II")

_STATE = Struct("<IIB")

_EDGE = Struct("<II")


# ============================================================
# DNS database
# ============================================================


class DNSDatabase:
    def __init__(
        self,
        filename,
        cache_size=16,
    ):
        self._filename = filename

        self._f = open(
            filename,
            "rb",
        )

        self._closed = False

        self._read_buf = bytearray(64)

        # QNAME parser workspace.
        #
        # uint16 packet offsets.
        self._qpos = array(
            "H",
            [0] * _MAX_NAME_LABELS,
        )

        # Label lengths.
        self._qlen = bytearray(_MAX_NAME_LABELS)

        # Small cache:
        #
        # hash -> label ID
        #
        # Only successful lookups are cached.
        self._cache_hash = array(
            "I",
            [0] * cache_size,
        )

        self._cache_id = array(
            "I",
            [0] * cache_size,
        )

        self._cache_used = 0

        self._cache_size = cache_size

        self._read_header()

    # ======================================
    # CPython/Micropython compatibility fix
    # ======================================
    def _read_into(self, f, buf, size):
        try:
            return f.readinto(buf, size)
        except TypeError:
            return f.readinto(memoryview(buf)[:size])


    # ========================================================
    # Raw file access (CPython/Micropython compatible)
    # ========================================================

    def _read(self, offset, size):

        f = self._f

        f.seek(offset)

        if size <= 64:
            n = self._read_into(
                f,
                self._read_buf,
                size,
            )

            if n != size:
                raise ValueError("truncated DNS database")

            return self._read_buf

        data = f.read(size)

        if len(data) != size:
            raise ValueError("truncated DNS database")

        return data

    # ========================================================
    # Header
    # ========================================================

    def _read_header(self):

        data = self._read(
            0,
            _HEADER.size,
        )

        (
            magic,
            version,
            flags,
            self.label_count,
            self.state_count,
            self.edge_count,
            self.name_count,
            self.label_bytes,
        ) = _HEADER.unpack_from(
            data,
            0,
        )

        if magic != _MAGIC:
            raise ValueError("not a DNSD database")

        if version != _VERSION:
            raise ValueError(f"unsupported DNSD version {version}")

        self._label_index = _HEADER.size

        self._label_data = self._label_index + self.label_count * _LABEL_INDEX.size

        self._state_offset = self._label_data + self.label_bytes

        self._edge_offset = self._state_offset + self.state_count * _STATE.size

        # Validate file size once.
        f = self._f

        f.seek(0, 2)

        size = f.tell()

        expected = self._edge_offset + self.edge_count * _EDGE.size

        if size < expected:
            raise ValueError("truncated DNS database")

        f.seek(0)

    # ========================================================
    # FNV-1a over a packet label
    # ========================================================

    @staticmethod
    def _hash_packet(
        packet,
        pos,
        length,
    ):

        h = _FNV_OFFSET

        end = pos + length

        while pos < end:
            c = packet[pos]

            if 65 <= c <= 90:
                c += 32

            h ^= c

            h = (h * _FNV_PRIME) & 0xFFFFFFFF

            pos += 1

        return h

    # ========================================================
    # FNV-1a over normal bytes
    # ========================================================

    @staticmethod
    def _hash_bytes(data):

        h = _FNV_OFFSET

        for c in data:
            if 65 <= c <= 90:
                c += 32

            h ^= c

            h = (h * _FNV_PRIME) & 0xFFFFFFFF

        return h

    # ========================================================
    # Label index lookup
    # ========================================================

    def _label_index_record(
        self,
        index,
    ):

        pos = self._label_index + index * _LABEL_INDEX.size

        data = self._read(
            pos,
            8,
        )

        h = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)

        offset = data[4] | (data[5] << 8) | (data[6] << 16) | (data[7] << 24)

        return h, offset

    # ========================================================
    # Compare database label against DNS packet label.
    #
    # Case insensitive.
    # ========================================================

    def _label_matches(
        self,
        label_offset,
        packet,
        packet_pos,
        packet_len,
    ):

        f = self._f

        f.seek(self._label_data + label_offset)

        length = f.read(1)

        if not length:
            return False

        length = length[0]

        if length != packet_len:
            return False

        i = 0

        while i < length:
            a = f.read(1)

            if not a:
                return False

            a = a[0]

            b = packet[packet_pos + i]

            if 65 <= a <= 90:
                a += 32

            if 65 <= b <= 90:
                b += 32

            if a != b:
                return False

            i += 1

        return True

    # ========================================================
    # Find label ID from DNS wire label.
    #
    # Returns:
    #
    #   >=0 label ID
    #   -1 not found
    # ========================================================

    def _find_packet_label(
        self,
        packet,
        pos,
        length,
    ):

        wanted_hash = self._hash_packet(
            packet,
            pos,
            length,
        )

        # ----------------------------------------------------
        # Tiny direct-mapped cache.
        # ----------------------------------------------------

        cache_size = self._cache_size

        if cache_size:
            slot = wanted_hash % cache_size

            if self._cache_hash[slot] == wanted_hash:
                label_id = self._cache_id[slot]

                h, offset = self._label_index_record(label_id)

                if h == wanted_hash and self._label_matches(
                    offset,
                    packet,
                    pos,
                    length,
                ):
                    return label_id

        # ----------------------------------------------------
        # Binary search by hash.
        # ----------------------------------------------------

        lo = 0
        hi = self.label_count

        while lo < hi:
            mid = (lo + hi) >> 1

            h, offset = self._label_index_record(mid)

            if h < wanted_hash:
                lo = mid + 1

            else:
                hi = mid

        # ----------------------------------------------------
        # Scan hash collisions.
        # ----------------------------------------------------

        index = lo

        while index < self.label_count:
            h, offset = self._label_index_record(index)

            if h != wanted_hash:
                break

            if self._label_matches(
                offset,
                packet,
                pos,
                length,
            ):
                if cache_size:
                    slot = wanted_hash % cache_size

                    self._cache_hash[slot] = wanted_hash

                    self._cache_id[slot] = index

                return index

            index += 1

        return -1

    # ========================================================
    # Find label from Python bytes.
    #
    # Convenience API.
    # ========================================================

    def _find_bytes_label(
        self,
        label,
    ):

        wanted_hash = self._hash_bytes(label)

        lo = 0
        hi = self.label_count

        while lo < hi:
            mid = (lo + hi) >> 1

            h, offset = self._label_index_record(mid)

            if h < wanted_hash:
                lo = mid + 1

            else:
                hi = mid

        index = lo

        while index < self.label_count:
            h, offset = self._label_index_record(index)

            if h != wanted_hash:
                break

            # Read stored label.
            f = self._f

            f.seek(self._label_data + offset)

            length = f.read(1)[0]

            if length == len(label):
                match = True

                i = 0

                while i < length:
                    a = f.read(1)[0]

                    b = label[i]

                    if 65 <= a <= 90:
                        a += 32

                    if 65 <= b <= 90:
                        b += 32

                    if a != b:
                        match = False
                        break

                    i += 1

                if match:
                    return index

            index += 1

        return -1

    # ========================================================
    # State
    # ========================================================

    def _state(self, state_id):
        pos = self._state_offset + state_id * _STATE.size
        data = self._read(pos, _STATE.size)
        return _STATE.unpack(data)


    # ========================================================
    # Edge
    # ========================================================

    def _edge(self, edge_number):
        pos = self._edge_offset + edge_number * _EDGE.size
        data = self._read(pos, _EDGE.size)
        return _EDGE.unpack(data)


    # ========================================================
    # Transition
    # ========================================================

    def _transition(
        self,
        state_id,
        label_id,
    ):

        first, count, _terminal = self._state(state_id)

        lo = 0
        hi = count

        while lo < hi:
            mid = (lo + hi) >> 1

            target, current = self._edge(first + mid)

            if current < label_id:
                lo = mid + 1

            elif current > label_id:
                hi = mid

            else:
                return target

        return -1

    # ========================================================
    # Parse DNS wire QNAME.
    #
    # Returns:
    #
    #     (label_count, next_offset)
    #
    # next_offset is the position immediately following the
    # original encoded QNAME.
    #
    # Compression pointers are followed.
    # ========================================================

    def _parse_qname(
        self,
        packet,
        offset,
    ):

        plen = len(packet)

        pos = offset

        count = 0

        expanded = 1

        jumped = False

        next_offset = -1

        pointer_hops = 0

        while True:
            if pos >= plen:
                raise ValueError("truncated DNS QNAME")

            length = packet[pos]

            # ------------------------------------------------
            # Compression pointer.
            # ------------------------------------------------

            if length & 0xC0 == 0xC0:
                if pos + 1 >= plen:
                    raise ValueError("truncated DNS pointer")

                pointer = ((length & 0x3F) << 8) | packet[pos + 1]

                if pointer >= plen:
                    raise ValueError("invalid DNS pointer")

                if not jumped:
                    next_offset = pos + 2

                    jumped = True

                pos = pointer

                pointer_hops += 1

                if pointer_hops > 16:
                    raise ValueError("DNS compression loop")

                continue

            # ------------------------------------------------
            # Reserved label form.
            # ------------------------------------------------

            if length & 0xC0:
                raise ValueError("invalid DNS label")

            # ------------------------------------------------
            # Root terminator.
            # ------------------------------------------------

            if length == 0:
                if not jumped:
                    next_offset = pos + 1

                return (
                    count,
                    next_offset,
                )

            if length > _MAX_LABEL:
                raise ValueError("DNS label too long")

            if pos + 1 + length > plen:
                raise ValueError("truncated DNS label")

            if count >= _MAX_NAME_LABELS:
                raise ValueError("too many DNS labels")

            # Store label position and length.
            self._qpos[count] = pos + 1

            self._qlen[count] = length

            count += 1

            expanded += 1 + length

            if expanded > _MAX_NAME_WIRE:
                raise ValueError("DNS name too long")

            pos += 1 + length

    # ========================================================
    # QNAME exact/parent lookup.
    #
    # parent=True:
    #
    #     example.com in database
    #
    # matches:
    #
    #     example.com
    #     www.example.com
    #     a.b.www.example.com
    # ========================================================

    def contains_qname(
        self,
        packet,
        offset=12,
        parent=False,
    ):

        count, next_offset = self._parse_qname(
            packet,
            offset,
        )

        if count == 0:
            return False

        state = 0

        i = count - 1

        while i >= 0:
            pos = self._qpos[i]

            length = self._qlen[i]

            label_id = self._find_packet_label(
                packet,
                pos,
                length,
            )

            if label_id < 0:
                return False

            state = self._transition(
                state,
                label_id,
            )

            if state < 0:
                return False

            if parent:
                first, edge_count, terminal = self._state(state)

                if terminal:
                    return True

            i -= 1

        if not parent:
            first, edge_count, terminal = self._state(state)

            return terminal != 0

        return False

    # ========================================================
    # Explicit parent API.
    # ========================================================

    def contains_qname_or_parent(
        self,
        packet,
        offset=12,
    ):

        return self.contains_qname(
            packet,
            offset,
            True,
        )

    # ========================================================
    # Normal string API.
    #
    # Intended for testing/debugging rather than the DNS hot
    # path.
    # ========================================================

    def contains(
        self,
        name,
    ):

        if isinstance(name, bytes):
            name = name.decode("ascii")

        labels = name.strip().rstrip(".").split(".")

        if not labels:
            return False

        state = 0

        i = len(labels) - 1

        while i >= 0:
            label_id = self._find_bytes_label(labels[i].encode("ascii"))

            if label_id < 0:
                return False

            state = self._transition(
                state,
                label_id,
            )

            if state < 0:
                return False

            i -= 1

        first, count, terminal = self._state(state)

        return terminal != 0

    def contains_or_parent(
        self,
        name,
    ):

        if isinstance(name, bytes):
            name = name.decode("ascii")

        labels = name.strip().rstrip(".").split(".")

        if not labels:
            return False

        state = 0

        i = len(labels) - 1

        while i >= 0:
            label_id = self._find_bytes_label(labels[i].encode("ascii"))

            if label_id < 0:
                return False

            state = self._transition(
                state,
                label_id,
            )

            if state < 0:
                return False

            first, count, terminal = self._state(state)

            if terminal:
                return True

            i -= 1

        return False

    # ========================================================
    # Statistics
    # ========================================================

    def stats(self):

        f = self._f

        f.seek(0, 2)

        size = f.tell()

        f.seek(0)

        return {
            "file": self._filename,
            "bytes": size,
            "names": self.name_count,
            "labels": self.label_count,
            "states": self.state_count,
            "edges": self.edge_count,
        }

    # ========================================================
    # Close
    # ========================================================

    def close(self):

        if self._closed:
            return

        self._closed = True

        self._f.close()

    def __enter__(self):

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):

        self.close()

    def __len__(self):

        return self.name_count

    def __contains__(
        self,
        name,
    ):

        return self.contains_or_parent(name)
