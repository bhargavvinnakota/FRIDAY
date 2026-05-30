import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class OpenClawTelegramOwnerTests(unittest.TestCase):
    def setUp(self):
        self._old_env = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["OPENCLAW_MESSAGE_INTENT_DIR"] = self.tmp.name
        os.environ.pop("FRIDAY_TELEGRAM_DIRECT", None)
        os.environ["OPENCLAW_TELEGRAM_OWNER"] = "openclaw"
        from friday.actions import comms
        self.comms = importlib.reload(comms)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.clear()
        os.environ.update(self._old_env)
        from friday.actions import comms
        importlib.reload(comms)

    def test_push_routes_to_openclaw_intent_without_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call blocked")):
            result = self.comms.telegram_push("hello from friday", chat_id="1234567890", silent=True)

        self.assertTrue(result["ok"])
        self.assertFalse(result["delivered"])
        self.assertTrue(result["routed_to_openclaw"])
        intent_path = Path(result["intent_path"])
        self.assertTrue(intent_path.exists())
        text = intent_path.read_text()
        self.assertIn('"source": "friday"', text)
        self.assertIn('"delivery_owner": "openclaw"', text)
        self.assertNotIn("1234567890", text)

    def test_get_updates_is_disabled_without_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call blocked")):
            self.assertEqual(self.comms.telegram_get_updates(timeout=1), [])

    def test_direct_mode_requires_two_explicit_flags(self):
        self.assertFalse(self.comms.telegram_direct_enabled())
        os.environ["FRIDAY_TELEGRAM_DIRECT"] = "1"
        importlib.reload(self.comms)
        self.assertFalse(self.comms.telegram_direct_enabled())
        os.environ["OPENCLAW_TELEGRAM_OWNER"] = "friday-legacy"
        importlib.reload(self.comms)
        self.assertTrue(self.comms.telegram_direct_enabled())


if __name__ == "__main__":
    unittest.main()
