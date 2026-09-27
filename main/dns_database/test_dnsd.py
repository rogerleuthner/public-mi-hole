# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import unittest

from dnsd import DNSDatabase


class TestDNSDatabase(unittest.TestCase):

    DB_PATH = "main/dns_database/dns.db"

    def setUp(self):
        self.db = DNSDatabase(self.DB_PATH)

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------
    # stats()
    # ------------------------------------------------------------------

    def test_stats_returns_value(self):
        """stats() should return database statistics."""
        stats = self.db.stats()

        self.assertIsNotNone(stats)

    def test_stats_returns_expected_type(self):
        """stats() should return a dictionary of statistics."""
        stats = self.db.stats()

        self.assertIsInstance(stats, dict)

    # ------------------------------------------------------------------
    # contains()
    # ------------------------------------------------------------------

    def test_contains_existing_domain(self):
        """contains() should return True for a domain in the database."""
        self.assertTrue(
            self.db.contains("example.com")
        )

    def test_contains_missing_domain(self):
        """contains() should return False for a domain not in the database."""
        self.assertFalse(
            self.db.contains("not-in-database.com")
        )

    def test_contains_unknown_subdomain(self):
        """contains() should not consider an unknown subdomain an exact match."""
        self.assertFalse(
            self.db.contains("www.example.com")
        )

    def test_contains_is_case_insensitive(self):
        """DNS names should normally be treated case-insensitively."""
        self.assertEqual(
            self.db.contains("example.com"),
            self.db.contains("EXAMPLE.COM")
        )

    def test_contains_empty_string(self):
        """An empty domain should not be considered a valid match."""
        self.assertFalse(
            self.db.contains("")
        )

    # ------------------------------------------------------------------
    # contains_or_parent()
    # ------------------------------------------------------------------

    def test_contains_or_parent_existing_domain(self):
        """contains_or_parent() should find an existing domain."""
        self.assertTrue(
            self.db.contains_or_parent("example.com")
        )

    def test_contains_or_parent_subdomain(self):
        """contains_or_parent() should find a matching parent domain."""
        self.assertTrue(
            self.db.contains_or_parent("www.example.com")
        )

    def test_contains_or_parent_deep_subdomain(self):
        """contains_or_parent() should find a matching parent several levels up."""
        self.assertTrue(
            self.db.contains_or_parent("a.b.www.example.com")
        )

    def test_contains_or_parent_missing_domain(self):
        """contains_or_parent() should return False when no parent exists."""
        self.assertFalse(
            self.db.contains_or_parent("not-in-database.com")
        )

    def test_contains_or_parent_unrelated_domain(self):
        """A different domain should not match an existing parent."""
        self.assertFalse(
            self.db.contains_or_parent("example.net")
        )

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def test_database_can_be_closed(self):
        """The database should be closable without raising an exception."""
        self.db.close()

        # Prevent tearDown() from closing it a second time if close()
        # is not idempotent.
        self.db = None

    def tearDown(self):
        if self.db is not None:
            self.db.close()


if __name__ == "__main__":
    unittest.main()