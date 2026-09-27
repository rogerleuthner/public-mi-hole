#!/usr/bin/env python3
# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import struct
import sys
from pathlib import Path

MAGIC = b"DNSD"
VERSION = 4

HEADER = struct.Struct("<4sBBIIIII")
LABEL_INDEX = struct.Struct("<II")
STATE = struct.Struct("<IIB")
EDGE = struct.Struct("<II")

FNV_OFFSET = 2166136261
FNV_PRIME = 16777619


def fnv1a(s):
    h = FNV_OFFSET
    for c in s:
        if 65 <= c <= 90:
            c += 32
        h ^= c
        h = (h * FNV_PRIME) & 0xffffffff
    return h


def normalize(name):
    name = name.strip()
    if name.endswith("."):
        name = name[:-1]
    if not name or name == ".":
        raise ValueError("invalid domain")

    labels = []
    wire = 1

    for part in name.split("."):
        if not part:
            raise ValueError("empty label")

        label = part.encode("idna").lower()

        if len(label) > 63:
            raise ValueError("label > 63 bytes")

        wire += 1 + len(label)
        labels.append(label)

    if wire > 255:
        raise ValueError("domain > 255 wire bytes")

    return tuple(reversed(labels))


class Node:
    __slots__ = ("children", "terminal", "canonical")

    def __init__(self):
        self.children = {}
        self.terminal = False
        self.canonical = None


def build(input_file, output_file):
    root = Node()
    labels = []
    label_ids = {}
    names = set()

    # --------------------------------------------------------
    # Read domains and build trie.
    # --------------------------------------------------------
    with open(input_file, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            try:
                parts = normalize(line)
            except (UnicodeError, ValueError) as e:
                raise ValueError(f"{input_file}:{line_no}: {e}")

            ids = []

            for label in parts:
                i = label_ids.get(label)
                if i is None:
                    i = len(labels)
                    label_ids[label] = i
                    labels.append(label)
                ids.append(i)

            ids = tuple(ids)

            if ids in names:
                continue
            names.add(ids)

            node = root
            for label_id in ids:
                node = node.children.setdefault(label_id, Node())
            node.terminal = True

    # --------------------------------------------------------
    # Minimize trie -> DAFSA.
    # --------------------------------------------------------
    registry = {}

    stack = [(root, False)]
    while stack:
        node, done = stack.pop()

        if not done:
            stack.append((node, True))
            stack.extend((child, False)
                         for child in node.children.values())
            continue

        sig = (
            node.terminal,
            tuple(sorted(
                (label_id, child.canonical)
                for label_id, child in node.children.items()
            )),
        )

        node.canonical = registry.setdefault(sig, node)

    root = root.canonical

    # --------------------------------------------------------
    # Assign final label IDs by (FNV-1a, label).
    # --------------------------------------------------------
    records = sorted(
        ((fnv1a(label), label, old_id)
         for old_id, label in enumerate(labels)),
        key=lambda x: (x[0], x[1]),
    )

    old_to_new = {}
    sorted_labels = []

    for new_id, (h, label, old_id) in enumerate(records):
        old_to_new[old_id] = new_id
        sorted_labels.append((h, label))

    # --------------------------------------------------------
    # Number canonical states.
    # --------------------------------------------------------
    states = []
    state_ids = {id(root): 0}
    queue = [root]

    for node in queue:
        states.append(node)

        for child in node.children.values():
            child = child.canonical
            key = id(child)

            if key not in state_ids:
                state_ids[key] = len(queue)
                queue.append(child)

    # --------------------------------------------------------
    # Build state + edge tables.
    # --------------------------------------------------------
    state_records = []
    edges = []

    for node in states:
        first = len(edges)

        transitions = [
            (
                old_to_new[label_id],
                state_ids[id(child.canonical)],
            )
            for label_id, child in node.children.items()
        ]

        transitions.sort()

        edges.extend(
            (target, label_id)
            for label_id, target in transitions
        )

        count = len(edges) - first

        state_records.append((
            first,
            count,
            int(node.terminal),
        ))

    # --------------------------------------------------------
    # Label data.
    # --------------------------------------------------------
    label_data = bytearray()
    label_index = bytearray()

    offset = 0

    for h, label in sorted_labels:
        label_index += LABEL_INDEX.pack(h, offset)
        label_data += bytes((len(label),)) + label
        offset += 1 + len(label)

    # --------------------------------------------------------
    # Write DNSD v3.
    # --------------------------------------------------------
    header = HEADER.pack(
        MAGIC,
        VERSION,
        0,
        len(sorted_labels),
        len(states),
        len(edges),
        len(names),
        len(label_data),
    )

    output = Path(output_file)
    with open(output, "wb") as f:
        f.write(header)
        f.write(label_index)
        f.write(label_data)

        for first, count, terminal in state_records:
            f.write(STATE.pack(first, count, terminal))

        for target, label_id in edges:
            f.write(EDGE.pack(target, label_id))

    print(
        f"{len(names):,} names, "
        f"{len(sorted_labels):,} labels, "
        f"{len(states):,} states, "
        f"{len(edges):,} edges -> {output}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} domains.txt dns.db")
        raise SystemExit(2)

    build(sys.argv[1], sys.argv[2])
