#!/usr/bin/env python3
"""Unit tests for scripts/token_monitor.py"""

import http.server
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

# Make the scripts directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import token_monitor


# ---------------------------------------------------------------------------
# calc_cost
# ---------------------------------------------------------------------------
class TestCalcCost(unittest.TestCase):
    """Tests for the calc_cost() pure function."""

    def test_known_model_basic(self):
        """deepseek-v4-flash with known token counts."""
        result = token_monitor.calc_cost(
            "deepseek-v4-flash",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=500_000,
        )
        self.assertIn("cost", result)
        self.assertIn("cost_cny", result)
        self.assertGreater(result["cost"], 0)
        self.assertAlmostEqual(
            result["cost_cny"], result["cost"] * token_monitor.USD_TO_CNY, places=4
        )

    def test_zero_tokens(self):
        result = token_monitor.calc_cost("deepseek-v4-flash", 0, 0, 0)
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["cost_cny"], 0)
        self.assertEqual(result["cache_hit_tokens"], 0)
        self.assertEqual(result["cache_miss_tokens"], 0)
        self.assertEqual(result["output_tokens"], 0)

    def test_none_tokens_treated_as_zero(self):
        result = token_monitor.calc_cost("deepseek-v4-flash", None, None, None)
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["output_tokens"], 0)

    def test_alias_deepseek_chat(self):
        """deepseek-chat should normalise to deepseek-v4-flash pricing."""
        r1 = token_monitor.calc_cost("deepseek-chat", 1_000_000, 1_000_000, 0)
        r2 = token_monitor.calc_cost("deepseek-v4-flash", 1_000_000, 1_000_000, 0)
        self.assertEqual(r1["cost"], r2["cost"])
        # display_name falls back to original model when normalised entry
        # lacks a display_name key
        self.assertEqual(r1["display_name"], "deepseek-chat")

    def test_alias_deepseek_reasoner(self):
        r1 = token_monitor.calc_cost("deepseek-reasoner", 1_000_000, 1_000_000, 0)
        r2 = token_monitor.calc_cost("deepseek-v4-flash", 1_000_000, 1_000_000, 0)
        self.assertEqual(r1["cost"], r2["cost"])

    def test_alias_mimo_v2_pro(self):
        """mimo-v2-pro normalises to mimo-v2.5-pro."""
        r1 = token_monitor.calc_cost("mimo-v2-pro", 1_000_000, 1_000_000, 0)
        r2 = token_monitor.calc_cost("mimo-v2.5-pro", 1_000_000, 1_000_000, 0)
        self.assertEqual(r1["cost"], r2["cost"])

    def test_alias_xiaomi_mimo_v25(self):
        """xiaomi/mimo-v2.5 normalises to mimo-v2.5."""
        r1 = token_monitor.calc_cost("xiaomi/mimo-v2.5", 1_000_000, 1_000_000, 0)
        r2 = token_monitor.calc_cost("mimo-v2.5", 1_000_000, 1_000_000, 0)
        self.assertEqual(r1["cost"], r2["cost"])

    def test_unknown_model_uses_fallback(self):
        result = token_monitor.calc_cost("unknown-model-xyz", 1_000_000, 1_000_000, 0)
        expected_cost = (
            1_000_000 / 1_000_000 * token_monitor.UNKNOWN_MODEL_PRICING["input_cache_miss"]
            + 1_000_000 / 1_000_000 * token_monitor.UNKNOWN_MODEL_PRICING["output"]
        )
        self.assertAlmostEqual(result["cost"], round(expected_cost, 6))

    def test_discount_flag_on_v4_pro(self):
        result = token_monitor.calc_cost("deepseek-v4-pro", 1_000_000, 1_000_000, 0)
        self.assertTrue(result["has_discount"])
        self.assertEqual(result["discount_pct"], 75)

    def test_no_discount_flag_on_flash(self):
        result = token_monitor.calc_cost("deepseek-v4-flash", 1_000_000, 1_000_000, 0)
        self.assertFalse(result["has_discount"])
        self.assertEqual(result["discount_pct"], 0)

    def test_cache_read_split(self):
        """cache_read_tokens go to 'cache_hit', input_tokens to 'cache_miss'."""
        result = token_monitor.calc_cost(
            "deepseek-v4-flash",
            input_tokens=2_000_000,
            output_tokens=0,
            cache_read_tokens=3_000_000,
        )
        self.assertEqual(result["cache_hit_tokens"], 3_000_000)
        self.assertEqual(result["cache_miss_tokens"], 2_000_000)

    def test_mimo_v25_pro_cost(self):
        """Validate MiMo v2.5 Pro pricing at exactly 1M tokens."""
        p = token_monitor.PRICING["mimo-v2.5-pro"]
        result = token_monitor.calc_cost("mimo-v2.5-pro", 1_000_000, 1_000_000, 1_000_000)
        expected = (
            1_000_000 / 1e6 * p["input_cache_hit"]
            + 1_000_000 / 1e6 * p["input_cache_miss"]
            + 1_000_000 / 1e6 * p["output"]
        )
        self.assertAlmostEqual(result["cost"], round(expected, 6))

    def test_mimo_v2_flash_cost(self):
        p = token_monitor.PRICING["mimo-v2-flash"]
        result = token_monitor.calc_cost("mimo-v2-flash", 500_000, 500_000, 500_000)
        expected = (
            500_000 / 1e6 * p["input_cache_hit"]
            + 500_000 / 1e6 * p["input_cache_miss"]
            + 500_000 / 1e6 * p["output"]
        )
        self.assertAlmostEqual(result["cost"], round(expected, 6))


# ---------------------------------------------------------------------------
# PRICING dict integrity
# ---------------------------------------------------------------------------
class TestPricingDict(unittest.TestCase):
    """Sanity checks on the PRICING dictionary."""

    def test_all_entries_have_required_keys(self):
        for model, p in token_monitor.PRICING.items():
            for key in ("input_cache_hit", "input_cache_miss", "output"):
                self.assertIn(key, p, f"{model} missing '{key}'")

    def test_prices_are_non_negative(self):
        for model, p in token_monitor.PRICING.items():
            self.assertGreaterEqual(p["input_cache_hit"], 0, model)
            self.assertGreaterEqual(p["input_cache_miss"], 0, model)
            self.assertGreaterEqual(p["output"], 0, model)

    def test_cache_hit_cheaper_than_miss(self):
        for model, p in token_monitor.PRICING.items():
            self.assertLessEqual(
                p["input_cache_hit"],
                p["input_cache_miss"],
                f"{model}: cache hit should be ≤ cache miss",
            )

    def test_default_pricing_all_zero(self):
        for v in token_monitor.DEFAULT_PRICING.values():
            self.assertEqual(v, 0.0)


# ---------------------------------------------------------------------------
# query_db with a temporary in-memory / temp-file SQLite
# ---------------------------------------------------------------------------
class TestQueryDB(unittest.TestCase):
    """Tests for query_db() using a temporary SQLite database."""

    def _create_db(self, path):
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                actual_cost_usd REAL DEFAULT 0,
                started_at INTEGER,
                ended_at INTEGER,
                title TEXT
            )
        """)
        return conn

    def test_missing_db_raises_file_not_found(self):
        with patch.object(token_monitor, "DB_PATH", "/tmp/nonexistent_db_12345.db"):
            with self.assertRaises(FileNotFoundError):
                token_monitor.query_db()

    def test_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            self._create_db(db_path).close()
            with patch.object(token_monitor, "DB_PATH", db_path):
                result = token_monitor.query_db()
                self.assertNotIn("error", result)
                self.assertEqual(result["summary"]["total_sessions"], 0)
                self.assertEqual(result["summary"]["total_input"], 0)
                self.assertEqual(result["sessions"], [])
                self.assertEqual(result["models"], [])
                self.assertIn("pricing", result)
                self.assertIn("updated_at", result)
        finally:
            os.unlink(db_path)

    def test_single_session(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = self._create_db(db_path)
            conn.execute(
                """INSERT INTO sessions
                   (id, source, model, input_tokens, output_tokens,
                    cache_read_tokens, started_at, ended_at, title)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("sess-1", "dingtalk", "deepseek-v4-flash", 100_000, 50_000,
                 80_000, 1700000000, 1700001000, "test session"),
            )
            conn.commit()
            conn.close()

            with patch.object(token_monitor, "DB_PATH", db_path):
                result = token_monitor.query_db()
                self.assertNotIn("error", result)
                self.assertEqual(result["summary"]["total_sessions"], 1)
                self.assertEqual(result["summary"]["total_input"], 100_000)
                self.assertEqual(result["summary"]["total_output"], 50_000)
                self.assertEqual(len(result["sessions"]), 1)
                sess = result["sessions"][0]
                self.assertEqual(sess["session_id"], "sess-1")
                self.assertIn("calculated_cost", sess)
                self.assertIn("calculated_cost_cny", sess)
                self.assertGreater(sess["calculated_cost"], 0)
        finally:
            os.unlink(db_path)

    def test_multiple_models_aggregation(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = self._create_db(db_path)
            conn.execute(
                """INSERT INTO sessions VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("s1", "wechat", "deepseek-v4-flash", 200_000, 100_000,
                 0, 0, 0, 0, 5, 0, 0, 1700000000, 1700001000, "a"),
            )
            conn.execute(
                """INSERT INTO sessions VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("s2", "dingtalk", "mimo-v2.5-pro", 300_000, 200_000,
                 100_000, 0, 0, 0, 10, 0, 0, 1700002000, 1700003000, "b"),
            )
            conn.commit()
            conn.close()

            with patch.object(token_monitor, "DB_PATH", db_path):
                result = token_monitor.query_db()
                self.assertEqual(result["summary"]["total_sessions"], 2)
                self.assertEqual(result["summary"]["total_input"], 500_000)
                self.assertEqual(result["summary"]["total_output"], 300_000)
                self.assertEqual(len(result["models"]), 2)
                self.assertGreater(result["summary"]["total_cost_cny"], 0)
        finally:
            os.unlink(db_path)

    def test_alias_models_merged_in_breakdown(self):
        """deepseek-chat sessions should merge into deepseek-v4-flash in model breakdown."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = self._create_db(db_path)
            for i, model in enumerate(["deepseek-chat", "deepseek-v4-flash"]):
                conn.execute(
                    """INSERT INTO sessions VALUES
                       (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"s{i}", "api", model, 100_000, 50_000,
                     0, 0, 0, 0, 1, 0, 0, 1700000000 + i, 1700001000 + i, f"m{i}"),
                )
            conn.commit()
            conn.close()

            with patch.object(token_monitor, "DB_PATH", db_path):
                result = token_monitor.query_db()
                model_names = [m["model"] for m in result["models"]]
                self.assertIn("deepseek-v4-flash", model_names)
                self.assertNotIn("deepseek-chat", model_names)
        finally:
            os.unlink(db_path)


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class TestHTTPHandler(unittest.TestCase):
    """Tests for the TokenMonitorHandler endpoints."""

    @classmethod
    def setUpClass(cls):
        # Create a temp DB for the handler to query
        cls._db_fd, cls._db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(cls._db_path)
        conn.execute("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                actual_cost_usd REAL DEFAULT 0,
                started_at INTEGER,
                ended_at INTEGER,
                title TEXT
            )
        """)
        conn.execute(
            """INSERT INTO sessions VALUES
               (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("s1", "test", "deepseek-v4-flash", 1000, 500,
             0, 0, 0, 0, 1, 0, 0, 1700000000, 1700001000, "test"),
        )
        conn.commit()
        conn.close()

        cls._orig_db_path = token_monitor.DB_PATH
        token_monitor.DB_PATH = cls._db_path

        cls._server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), token_monitor.TokenMonitorHandler
        )
        cls._port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever)
        cls._thread.daemon = True
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._thread.join(timeout=5)
        token_monitor.DB_PATH = cls._orig_db_path
        os.close(cls._db_fd)
        os.unlink(cls._db_path)

    def _get(self, path):
        url = f"http://127.0.0.1:{self._port}{path}"
        with urlopen(url, timeout=5) as resp:
            return resp.status, resp.read(), resp.headers

    def test_health_endpoint(self):
        status, body, headers = self._get("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["status"], "ok")
        self.assertIn("time", data)

    def test_data_endpoint(self):
        status, body, headers = self._get("/api/data")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        data = json.loads(body)
        self.assertIn("summary", data)
        self.assertIn("sessions", data)
        self.assertIn("models", data)
        self.assertIn("pricing", data)
        self.assertEqual(data["summary"]["total_sessions"], 1)

    def test_root_returns_html(self):
        status, body, headers = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"<!DOCTYPE html>", body)

    def test_cors_header_on_data(self):
        _, _, headers = self._get("/api/data")
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1")

    def test_cache_control_on_data(self):
        _, _, headers = self._get("/api/data")
        self.assertEqual(headers.get("Cache-Control"), "no-cache")


if __name__ == "__main__":
    unittest.main()
