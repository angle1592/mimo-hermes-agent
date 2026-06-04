#!/usr/bin/env python3
"""Unit tests for the sanitize_file() logic in scripts/sync.sh.

Since sync.sh is a bash script, we test the regex sanitisation by running
the sed commands via subprocess and verifying the output.
"""

import os
import subprocess
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYNC_SCRIPT = os.path.join(REPO_ROOT, "scripts", "sync.sh")


def _sanitize(content: str) -> str:
    """Write *content* to a temp file, run the sanitize_file sed from sync.sh,
    and return the resulting text."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp = f.name
    try:
        # Extract the exact sed expression from sync.sh and apply it
        cmd = (
            f"sed -i -E "
            f"-e 's/cid[A-Za-z0-9+/=]{{10,}}/REDACTED_CHAT_ID/g' "
            f"-e 's/47\\.119\\.146\\.[0-9]+/YOUR_SERVER_IP/g' "
            f"-e 's/ghp_[A-Za-z0-9]+/REDACTED_PAT/g' "
            f"-e 's/sk-[A-Za-z0-9]{{20,}}/REDACTED_KEY/g' "
            f"""-e 's/(chat_id:REDACTED
            f"""-e 's/(app_key:REDACTED
            f"""-e 's/(app_secret:REDACTED
            f"""-e 's/(api_key:""
            f"""-e 's/(client_secret:REDACTED
            f"""-e 's/(record_key:FILL_IN
            f"{tmp}"
        )
        subprocess.run(["bash", "-c", cmd], check=True)
        with open(tmp, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(tmp)


class TestSanitizeFile(unittest.TestCase):
    """Test the sed-based sanitisation patterns from sync.sh."""

    def test_redacts_github_pat(self):
        text = "token: REDACTED_PAT"
        result = _sanitize(text)
        self.assertNotIn("REDACTED_PAT", result)
        self.assertIn("REDACTED_PAT", result)

    def test_redacts_sk_api_key(self):
        text = "DEEPSEEK_API_KEY=REDACTED_KEY"
        result = _sanitize(text)
        self.assertNotIn("REDACTED_KEY", result)
        self.assertIn("REDACTED_KEY", result)

    def test_redacts_server_ip(self):
        text = "server: YOUR_SERVER_IP"
        result = _sanitize(text)
        self.assertNotIn("YOUR_SERVER_IP", result)
        self.assertIn("YOUR_SERVER_IP", result)

    def test_redacts_chat_id_long(self):
        text = "REDACTED_CHAT_ID"
        result = _sanitize(text)
        self.assertIn("REDACTED_CHAT_ID", result)

    def test_redacts_yaml_chat_id_field(self):
        text = "chat_id: REDACTED
        result = _sanitize(text)
        self.assertIn("chat_id:REDACTED
        self.assertIn("REDACTED", result)
        self.assertNotIn("some_secret_id_12345", result)

    def test_redacts_app_key(self):
        text = "app_key: REDACTED
        result = _sanitize(text)
        self.assertIn("app_key:REDACTED
        self.assertIn("REDACTED", result)
        self.assertNotIn("ding_abc123", result)

    def test_redacts_app_secret(self):
        text = "app_secret: REDACTED
        result = _sanitize(text)
        self.assertIn("app_secret:REDACTED
        self.assertIn("REDACTED", result)
        self.assertNotIn("super_secret_value", result)

    def test_redacts_api_key_yaml(self):
        text = 'api_key: ""
        result = _sanitize(text)
        self.assertIn("api_key:""
        self.assertIn('""', result)

    def test_redacts_client_secret(self):
        text = "client_secret: REDACTED
        result = _sanitize(text)
        self.assertIn("client_secret:REDACTED
        self.assertIn("REDACTED", result)
        self.assertNotIn("my_oauth_secret", result)

    def test_redacts_record_key(self):
        text = "record_key: FILL_IN
        result = _sanitize(text)
        self.assertIn("record_key:FILL_IN
        self.assertIn("FILL_IN", result)
        self.assertNotIn("cypress_key_123", result)

    def test_leaves_safe_text_untouched(self):
        text = "This is normal documentation text.\nNo secrets here."
        result = _sanitize(text)
        self.assertEqual(result, text)

    def test_multiple_patterns_in_one_file(self):
        text = textwrap.dedent("""\
            server: YOUR_SERVER_IP
            token: REDACTED_PAT
            api_key: ""
            app_secret: REDACTED
        """)
        result = _sanitize(text)
        self.assertNotIn("YOUR_SERVER_IP", result)
        self.assertNotIn("ghp_", result)
        self.assertNotIn("dingtalk_secret", result)
        self.assertIn("YOUR_SERVER_IP", result)
        self.assertIn("REDACTED_PAT", result)

    def test_short_sk_key_not_redacted(self):
        """sk- followed by <20 chars should NOT be redacted."""
        text = "sk-short"
        result = _sanitize(text)
        self.assertIn("sk-short", result)

    def test_short_cid_not_redacted(self):
        """cid followed by <10 chars should NOT be redacted."""
        text = "cidShort"
        result = _sanitize(text)
        self.assertIn("cidShort", result)


class TestSyncScriptExists(unittest.TestCase):
    """Basic sanity checks on sync.sh."""

    def test_script_exists(self):
        self.assertTrue(os.path.isfile(SYNC_SCRIPT))

    def test_script_is_executable_or_readable(self):
        self.assertTrue(os.access(SYNC_SCRIPT, os.R_OK))

    def test_script_has_shebang(self):
        with open(SYNC_SCRIPT) as f:
            first_line = f.readline()
        self.assertTrue(first_line.startswith("#!/"))

    def test_dry_run_flag_documented(self):
        """The script should support --dry-run."""
        with open(SYNC_SCRIPT) as f:
            content = f.read()
        self.assertIn("--dry-run", content)


if __name__ == "__main__":
    unittest.main()
