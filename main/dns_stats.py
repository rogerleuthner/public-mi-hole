# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

"""Bounded DNS telemetry for the Mi-Hole firmware."""

import time

class DNSStats:
    """Collect bounded DNS statistics in RAM."""

    def __init__(
        self,
        activity_size=100,
        max_domains=64,
        max_clients=32,
    ):
        self.activity_size = activity_size
        self.max_domains = max_domains
        self.max_clients = max_clients

        self.started_ms = time.ticks_ms()

        self.total_queries = 0
        self.blocked_queries = 0
        self.allowed_queries = 0
        self.forwarded_queries = 0

        self.upstream_responses = 0
        self.upstream_timeouts = 0
        self.upstream_errors = 0

        self.latency_total_ms = 0
        self.latency_count = 0
        self.latency_max_ms = 0

        self._activity = [None] * activity_size
        self._activity_index = 0
        self._activity_count = 0

        self._blocked_domains = {}
        self._clients = {}

        self._next_activity_id = 1

    # ============================================================
    # Recording
    # ============================================================

    def record_query(
        self,
        domain,
        client,
        blocked,
    ):
        """Record a newly received DNS query.

        Returns an activity ID used to update the same activity
        record when forwarding completes, times out, or fails.
        """
        activity_id = self._next_activity_id

        self._next_activity_id += 1

        if self._next_activity_id > 0x7FFFFFFF:
            self._next_activity_id = 1

        self.total_queries += 1

        self._increment_client(client)

        if blocked:
            self.blocked_queries += 1
            self._increment_domain(domain)

            action = "blocked"
        else:
            self.allowed_queries += 1
            self.forwarded_queries += 1

            action = "forwarded"

        self._add_activity(
            activity_id=activity_id,
            domain=domain,
            client=client,
            action=action,
            latency_ms=0,
            match=None,
        )

        return activity_id

    def record_response(
        self,
        activity_id,
        latency_ms,
    ):
        """Record a successful upstream response."""
        self.upstream_responses += 1

        self.latency_total_ms += latency_ms
        self.latency_count += 1

        if latency_ms > self.latency_max_ms:
            self.latency_max_ms = latency_ms

        self._update_activity(
            activity_id,
            action="allowed",
            latency_ms=latency_ms,
        )

    def record_timeout(
        self,
        activity_id,
    ):
        """Record an upstream timeout."""
        self.upstream_timeouts += 1

        self._update_activity(
            activity_id,
            action="timeout",
            latency_ms=0,
        )

    def record_error(
        self,
        activity_id,
    ):
        """Record an upstream/socket error."""
        self.upstream_errors += 1

        self._update_activity(
            activity_id,
            action="error",
            latency_ms=0,
        )

    # ============================================================
    # Snapshots
    # ============================================================

    def snapshot(self):
        """Return a JSON-friendly statistics snapshot."""
        if self.total_queries:
            block_rate = (
                self.blocked_queries
                * 100.0
                / self.total_queries
            )
        else:
            block_rate = 0.0

        if self.latency_count:
            average_latency = (
                self.latency_total_ms
                / self.latency_count
            )
        else:
            average_latency = 0.0

        return {
            "uptime_ms": self._uptime_ms(),
            "queries": self.total_queries,
            "blocked": self.blocked_queries,
            "allowed": self.allowed_queries,
            "forwarded": self.forwarded_queries,
            "responses": self.upstream_responses,
            "timeouts": self.upstream_timeouts,
            "errors": self.upstream_errors,
            "block_rate": round(block_rate, 2),
            "latency_avg_ms": round(
                average_latency,
                2,
            ),
            "latency_max_ms": self.latency_max_ms,
            "active_clients": len(self._clients),
            "tracked_domains": len(
                self._blocked_domains
            ),
        }

    def activity(
        self,
        limit=50,
    ):
        """Return the newest activity entries first."""
        if limit < 1:
            limit = 1

        if limit > self.activity_size:
            limit = self.activity_size

        if self._activity_count == 0:
            return []

        count = min(
            limit,
            self._activity_count,
        )

        result = []

        start = (
            self._activity_index - count
        ) % self.activity_size

        for offset in range(count):
            index = (
                start + offset
            ) % self.activity_size

            item = self._activity[index]

            if item is not None:
                result.append(
                    self._activity_to_dict(item)
                )

        result.reverse()

        return result

    def top_domains(
        self,
        limit=10,
    ):
        """Return the most frequently blocked domains."""
        return self._top_items(
            self._blocked_domains,
            limit,
        )

    def top_clients(
        self,
        limit=10,
    ):
        """Return the clients with the most DNS queries."""
        return self._top_items(
            self._clients,
            limit,
        )

    def reset(self):
        """Clear telemetry without restarting the DNS server."""
        self.started_ms = time.ticks_ms()

        self.total_queries = 0
        self.blocked_queries = 0
        self.allowed_queries = 0
        self.forwarded_queries = 0

        self.upstream_responses = 0
        self.upstream_timeouts = 0
        self.upstream_errors = 0

        self.latency_total_ms = 0
        self.latency_count = 0
        self.latency_max_ms = 0

        self._activity = [None] * self.activity_size
        self._activity_index = 0
        self._activity_count = 0

        self._blocked_domains.clear()
        self._clients.clear()

    # ============================================================
    # Internal helpers
    # ============================================================

    def _uptime_ms(self):
        return time.ticks_diff(
            time.ticks_ms(),
            self.started_ms,
        )

    def _add_activity(
        self,
        activity_id,
        domain,
        client,
        action,
        latency_ms,
        match,
    ):
        item = (
            activity_id,
            self._uptime_ms(),
            domain,
            client,
            action,
            latency_ms,
            match,
        )

        self._activity[
            self._activity_index
        ] = item

        self._activity_index = (
            self._activity_index + 1
        ) % self.activity_size

        if self._activity_count < self.activity_size:
            self._activity_count += 1

    def _update_activity(
        self,
        activity_id,
        action,
        latency_ms,
    ):
        for index in range(
            self.activity_size
        ):
            item = self._activity[index]

            if item is None:
                continue

            if item[0] != activity_id:
                continue

            (
                item_id,
                uptime_ms,
                domain,
                client,
                _old_action,
                _old_latency,
                match,
            ) = item

            self._activity[index] = (
                item_id,
                uptime_ms,
                domain,
                client,
                action,
                latency_ms,
                match,
            )

            return

    def _increment_domain(
        self,
        domain,
    ):
        self._increment_bounded(
            self._blocked_domains,
            domain,
            self.max_domains,
        )

    def _increment_client(
        self,
        client,
    ):
        current = self._clients.get(client)

        if current is not None:
            self._clients[client] = (
                current + 1
            )
            return

        if len(self._clients) >= self.max_clients:
            self._remove_smallest(
                self._clients
            )

        self._clients[client] = 1

    @staticmethod
    def _increment_bounded(
        mapping,
        key,
        maximum,
    ):
        current = mapping.get(key)

        if current is not None:
            mapping[key] = current + 1
            return

        if len(mapping) >= maximum:
            DNSStats._remove_smallest(
                mapping
            )

        mapping[key] = 1

    @staticmethod
    def _remove_smallest(mapping):
        smallest_key = None
        smallest_value = None

        for key, value in mapping.items():
            if (
                smallest_value is None
                or value < smallest_value
            ):
                smallest_key = key
                smallest_value = value

        if smallest_key is not None:
            del mapping[smallest_key]

    @staticmethod
    def _top_items(
        mapping,
        limit,
    ):
        if limit < 1:
            return []

        items = []

        for name, count in mapping.items():
            items.append(
                {
                    "name": name,
                    "count": count,
                }
            )

        items.sort(
            key=lambda item: item["count"],
            reverse=True,
        )

        return items[:limit]

    @staticmethod
    def _activity_to_dict(item):
        (
            activity_id,
            uptime_ms,
            domain,
            client,
            action,
            latency_ms,
            match,
        ) = item

        return {
            "id": activity_id,
            "uptime_ms": uptime_ms,
            "domain": domain,
            "client": client,
            "action": action,
            "latency_ms": latency_ms,
            "match": match,
        }