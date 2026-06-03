#!/usr/bin/env python3
"""Unit tests for skills/devops/deploy-service-china/scripts/seed-posture-data.py"""

import os
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta
from unittest.mock import patch

# Make the script importable
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "skills",
        "devops",
        "deploy-service-china",
        "scripts",
    ),
)

# The file is named with hyphens; use importlib to load it.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "seed_posture_data",
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "skills",
        "devops",
        "deploy-service-china",
        "scripts",
        "seed-posture-data.py",
    ),
)
seed_posture_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_posture_data)


# ---------------------------------------------------------------------------
# _generate_day_episodes
# ---------------------------------------------------------------------------
class TestGenerateDayEpisodes(unittest.TestCase):
    """Tests for _generate_day_episodes()."""

    def test_returns_wake_sleep_episodes(self):
        from datetime import date

        cfg = seed_posture_data.WEEK_EPISODES[1]
        wake, sleep, episodes = seed_posture_data._generate_day_episodes(
            date(2026, 5, 5), cfg  # Monday
        )
        self.assertIsInstance(wake, float)
        self.assertIsInstance(sleep, float)
        self.assertIsInstance(episodes, list)
        self.assertGreater(sleep, wake)

    def test_weekday_wake_range(self):
        """Weekday wake time should be between 7.0 and 8.5."""
        import random
        from datetime import date

        random.seed(42)
        cfg = seed_posture_data.WEEK_EPISODES[1]
        for _ in range(50):
            wake, _, _ = seed_posture_data._generate_day_episodes(
                date(2026, 5, 5), cfg  # Monday
            )
            self.assertGreaterEqual(wake, 7.0)
            self.assertLessEqual(wake, 8.5)

    def test_weekend_wake_range(self):
        """Weekend wake time should be between 9.0 and 10.5."""
        import random
        from datetime import date

        random.seed(42)
        cfg = seed_posture_data.WEEK_EPISODES[1]
        for _ in range(50):
            wake, _, _ = seed_posture_data._generate_day_episodes(
                date(2026, 5, 10), cfg  # Saturday
            )
            self.assertGreaterEqual(wake, 9.0)
            self.assertLessEqual(wake, 10.5)

    def test_episode_count_within_config_bounds(self):
        import random
        from datetime import date

        random.seed(42)
        for week_num, cfg in seed_posture_data.WEEK_EPISODES.items():
            _, _, episodes = seed_posture_data._generate_day_episodes(
                date(2026, 5, 5), cfg
            )
            self.assertGreaterEqual(len(episodes), cfg["count"][0])
            self.assertLessEqual(len(episodes), cfg["count"][1])

    def test_episodes_sorted_by_start_time(self):
        import random
        from datetime import date

        random.seed(99)
        cfg = seed_posture_data.WEEK_EPISODES[1]
        _, _, episodes = seed_posture_data._generate_day_episodes(
            date(2026, 5, 5), cfg
        )
        starts = [e[0] for e in episodes]
        self.assertEqual(starts, sorted(starts))

    def test_episode_types_are_valid(self):
        import random
        from datetime import date

        random.seed(7)
        cfg = seed_posture_data.WEEK_EPISODES[2]
        _, _, episodes = seed_posture_data._generate_day_episodes(
            date(2026, 5, 5), cfg
        )
        for start, end, ptype in episodes:
            self.assertIn(ptype, ("head_down", "hunchback"))
            self.assertGreater(end, start)


# ---------------------------------------------------------------------------
# generate_records
# ---------------------------------------------------------------------------
class TestGenerateRecords(unittest.TestCase):
    """Tests for generate_records()."""

    def test_reminder_mode_produces_records(self):
        records = seed_posture_data.generate_records(
            days=3, start_date="2026-05-01", seed=42, mode="reminder"
        )
        self.assertGreater(len(records), 0)

    def test_ratio_mode_produces_records(self):
        records = seed_posture_data.generate_records(
            days=3, start_date="2026-05-01", seed=42, mode="ratio"
        )
        self.assertGreater(len(records), 0)

    def test_deterministic_with_seed(self):
        r1 = seed_posture_data.generate_records(days=2, start_date="2026-05-01", seed=123)
        r2 = seed_posture_data.generate_records(days=2, start_date="2026-05-01", seed=123)
        self.assertEqual(len(r1), len(r2))
        # Compare posture types
        types1 = [r[1] for r in r1]
        types2 = [r[1] for r in r2]
        self.assertEqual(types1, types2)

    def test_record_tuple_structure(self):
        records = seed_posture_data.generate_records(
            days=1, start_date="2026-05-01", seed=1, mode="reminder"
        )
        for rec in records[:10]:
            self.assertEqual(len(rec), 7)
            device, posture, person_present, lux, fill, onenet_ts, created_ts = rec
            self.assertEqual(device, "main")
            self.assertIn(posture, ("normal", "head_down", "hunchback", "no_person"))
            self.assertIn(person_present, (0, 1))
            self.assertIn(fill, (0, 1))

    def test_posture_types_include_abnormal(self):
        """With enough records, we should see at least some abnormal posture."""
        records = seed_posture_data.generate_records(
            days=7, start_date="2026-05-01", seed=42, mode="reminder"
        )
        types = Counter(r[1] for r in records)
        self.assertGreater(types.get("normal", 0), 0)
        self.assertGreater(
            types.get("head_down", 0) + types.get("hunchback", 0),
            0,
            "Expected some abnormal posture records",
        )

    def test_timestamps_are_ascending(self):
        records = seed_posture_data.generate_records(
            days=2, start_date="2026-05-01", seed=42, mode="reminder"
        )
        created_times = [r[6] for r in records]
        for i in range(1, len(created_times)):
            self.assertGreaterEqual(created_times[i], created_times[i - 1])

    def test_no_records_beyond_now(self):
        """All records should have timestamps ≤ now."""
        now = datetime.now()
        records = seed_posture_data.generate_records(
            days=7, start_date="2026-05-01", seed=42, mode="reminder"
        )
        for rec in records:
            self.assertLessEqual(rec[6], now + timedelta(seconds=120))

    def test_week_profiles_exist(self):
        for week in (1, 2, 3):
            self.assertIn(week, seed_posture_data.WEEK_PROFILES)
            self.assertIn(week, seed_posture_data.WEEK_EPISODES)

    def test_week_episodes_improvement_trend(self):
        """Later weeks should have fewer abnormal episodes configured."""
        w1 = seed_posture_data.WEEK_EPISODES[1]["count"]
        w3 = seed_posture_data.WEEK_EPISODES[3]["count"]
        # Week 3 max should be less than Week 1 min
        self.assertLess(w3[1], w1[0])


# ---------------------------------------------------------------------------
# main() / CLI
# ---------------------------------------------------------------------------
class TestSeedPostureDataCLI(unittest.TestCase):
    """Test the CLI output of seed-posture-data.py main()."""

    def test_sql_file_output(self):
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False, mode="w") as f:
            sql_path = f.name
        try:
            test_args = [
                "seed-posture-data.py",
                "--days", "2",
                "--start-date", "2026-05-01",
                "--seed", "42",
                "--sql-file", sql_path,
                "--database", "testdb",
                "--table", "test_table",
            ]
            with patch.object(sys, "argv", test_args):
                seed_posture_data.main()
            with open(sql_path) as f:
                sql = f.read()
            self.assertIn("USE testdb;", sql)
            self.assertIn("TRUNCATE TABLE test_table;", sql)
            self.assertIn("INSERT INTO test_table", sql)
            self.assertIn("VALUES", sql)
        finally:
            os.unlink(sql_path)

    def test_output_file_flag(self):
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False, mode="w") as f:
            out_path = f.name
        try:
            test_args = [
                "seed-posture-data.py",
                "--days", "1",
                "--start-date", "2026-05-01",
                "--seed", "1",
                "--output", out_path,
            ]
            with patch.object(sys, "argv", test_args):
                seed_posture_data.main()
            with open(out_path) as f:
                sql = f.read()
            self.assertIn("INSERT INTO posture_records", sql)
        finally:
            os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
