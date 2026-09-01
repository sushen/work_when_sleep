"""Unit tests for GroupLifecycleManager in search_interested.group_lifecycle."""

from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path

from search_interested.group_lifecycle import GroupLifecycleManager


class TestGroupLifecycleManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.stats_file = self.temp_path / "group_stats.json"
        self.group_list_file = self.temp_path / "groupList.txt"
        self.inactive_groups_file = self.temp_path / "inactive_groups.txt"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_stats_file_starts_fresh(self):
        manager = GroupLifecycleManager(
            stats_file=self.stats_file,
            group_list_file=self.group_list_file,
            inactive_groups_file=self.inactive_groups_file,
        )
        self.assertEqual(manager.stats, {})
        self.assertFalse(self.stats_file.exists())

    def test_record_scan_result_with_strong_opportunity(self):
        manager = GroupLifecycleManager(
            stats_file=self.stats_file,
            group_list_file=self.group_list_file,
            inactive_groups_file=self.inactive_groups_file,
        )
        group_url = "https://facebook.com/groups/testgroup1"
        opportunities = [
            {"quality": "STRONG", "content_text": "Need Python dev"},
            {"quality": "WEAK", "content_text": "Just saying hi"},
        ]

        today_str = datetime.date.today().isoformat()
        stats = manager.record_scan_result(group_url, opportunities)

        self.assertEqual(stats["last_scanned_date"], today_str)
        self.assertEqual(stats["last_strong_possible_date"], today_str)
        self.assertEqual(stats["total_opportunities_found"], 1)
        self.assertEqual(stats["consecutive_empty_scans"], 0)

        # Confirm atomic file persistence
        self.assertTrue(self.stats_file.exists())
        with open(self.stats_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(group_url, data)
        self.assertEqual(data[group_url]["total_opportunities_found"], 1)

    def test_record_scan_result_empty_or_weak(self):
        manager = GroupLifecycleManager(
            stats_file=self.stats_file,
            group_list_file=self.group_list_file,
            inactive_groups_file=self.inactive_groups_file,
        )
        group_url = "https://facebook.com/groups/testgroup2"

        # First scan with strong opp
        manager.record_scan_result(group_url, [{"quality": "POSSIBLE"}])
        first_opp_date = manager.stats[group_url]["last_strong_possible_date"]

        # Second scan with empty list
        stats = manager.record_scan_result(group_url, [])
        self.assertEqual(stats["last_strong_possible_date"], first_opp_date)
        self.assertEqual(stats["consecutive_empty_scans"], 1)
        self.assertEqual(stats["total_opportunities_found"], 1)

        # Third scan with WEAK opp only
        stats = manager.record_scan_result(group_url, [{"quality": "WEAK"}])
        self.assertEqual(stats["consecutive_empty_scans"], 2)
        self.assertEqual(stats["total_opportunities_found"], 1)

    def test_prune_inactive_groups_14_day_rule(self):
        group1 = "https://facebook.com/groups/active1"
        group2 = "https://facebook.com/groups/dead1"
        group3 = "https://facebook.com/groups/dead_never_found"

        # Write active groups file
        self.group_list_file.write_text(f"{group1}\n{group2}\n{group3}\n")

        today = datetime.date.today()
        recent_date = (today - datetime.timedelta(days=5)).isoformat()
        old_date = (today - datetime.timedelta(days=15)).isoformat()
        scan_date = today.isoformat()

        initial_stats = {
            group1: {
                "last_scanned_date": scan_date,
                "last_strong_possible_date": recent_date,
                "total_opportunities_found": 3,
                "consecutive_empty_scans": 0,
            },
            group2: {
                "last_scanned_date": scan_date,
                "last_strong_possible_date": old_date,
                "total_opportunities_found": 1,
                "consecutive_empty_scans": 5,
            },
            group3: {
                "last_scanned_date": scan_date,
                "last_strong_possible_date": None,
                "total_opportunities_found": 0,
                "consecutive_empty_scans": 3,
            },
        }

        self.stats_file.write_text(json.dumps(initial_stats))

        manager = GroupLifecycleManager(
            stats_file=self.stats_file,
            group_list_file=self.group_list_file,
            inactive_groups_file=self.inactive_groups_file,
            max_inactive_days=14,
        )

        pruned = manager.prune_inactive_groups()
        self.assertIn(group2, pruned)
        self.assertIn(group3, pruned)
        self.assertNotIn(group1, pruned)

        # Verify active group list
        active_lines = self.group_list_file.read_text().splitlines()
        self.assertIn(group1, active_lines)
        self.assertNotIn(group2, active_lines)
        self.assertNotIn(group3, active_lines)

        # Verify inactive group list
        inactive_lines = self.inactive_groups_file.read_text().splitlines()
        self.assertIn(group2, inactive_lines)
        self.assertIn(group3, inactive_lines)

    def test_on_group_scanned_helper(self):
        group_url = "https://facebook.com/groups/scanned_group"
        self.group_list_file.write_text(f"{group_url}\n")

        manager = GroupLifecycleManager(
            stats_file=self.stats_file,
            group_list_file=self.group_list_file,
            inactive_groups_file=self.inactive_groups_file,
        )

        stats = manager.on_group_scanned(group_url, [{"quality": "STRONG"}])
        self.assertEqual(stats["total_opportunities_found"], 1)
        self.assertEqual(stats["consecutive_empty_scans"], 0)


if __name__ == "__main__":
    unittest.main()
