import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent import Store, DemoApps, LiveApps, ReviewRequired, run_agent, gmail_message, message_text

EMAIL = {"id": "mail-123", "sender": "alex@example.com", "subject": "Production outage", "body": "Our entire team cannot log in."}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.db")

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_happy_path_reads_back(self):
        r = run_agent(self.store, EMAIL)
        self.assertEqual(r["state"], "verified")
        self.assertEqual(r["expected"]["status"], "Open")
        self.assertIn("Verify ticket", [e["stage"] for e in r["events"]])
        self.assertIn("Verify notification", [e["stage"] for e in r["events"]])

    def test_priority_repair(self):
        r = run_agent(self.store, EMAIL, fault="priority")
        self.assertEqual(r["state"], "verified")
        mismatch = next(e for e in r["events"] if e["state"] == "mismatch")
        self.assertEqual(mismatch["detail"]["priority"], {"expected": "High", "actual": "Low"})
        self.assertEqual(self.store.get("demo:" + r["ticket_id"])["priority"], "High")

    def test_notification_repair(self):
        r = run_agent(self.store, EMAIL, fault="notification")
        self.assertEqual(r["state"], "verified")
        self.assertTrue(any(e["stage"] == "Repair notification" for e in r["events"]))

    def test_persistent_failure_stops_before_notification(self):
        r = run_agent(self.store, EMAIL, fault="persistent")
        self.assertEqual(r["state"], "needs_review")
        self.assertNotIn("message_id", r)
        self.assertEqual(sum(e["stage"] == "Repair ticket" for e in r["events"]), 2)

    def test_duplicate_run_reuses_objects(self):
        a = run_agent(self.store, EMAIL, fault="priority")
        b = run_agent(self.store, EMAIL)
        self.assertEqual(a["ticket_id"], b["ticket_id"])
        self.assertEqual(a["message_id"], b["message_id"])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM kv WHERE key LIKE 'demo:%'").fetchone()[0], 2)

    def test_persistence_after_restart(self):
        a = run_agent(self.store, EMAIL)
        self.store.db.close()
        self.store = Store(Path(self.temp.name) / "test.db")
        b = run_agent(self.store, EMAIL)
        self.assertEqual(a["message_id"], b["message_id"])

    def test_uncertain_create_is_never_blindly_repeated(self):
        apps = DemoApps(self.store)
        def create_then_timeout(expected):
            apps.create_ticket_original(expected)
            raise ReviewRequired("Timed out after provider accepted the write")
        apps.create_ticket_original = apps.create_ticket
        apps.create_ticket = create_then_timeout
        a = run_agent(self.store, EMAIL, apps=apps)
        b = run_agent(self.store, EMAIL)
        self.assertEqual(a["ticket_id"], "uncertain")
        self.assertEqual(b["state"], "needs_review")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM kv WHERE key LIKE 'demo:ticket-%'").fetchone()[0], 1)

    def test_source_id_conflicting_content_rejected(self):
        run_agent(self.store, EMAIL)
        with self.assertRaises(ValueError):
            run_agent(self.store, {**EMAIL, "body": "Different request"})

    def test_empty_email_rejected(self):
        with self.assertRaises(ValueError):
            run_agent(self.store, {**EMAIL, "body": " "})

    def test_live_fault_rejected(self):
        with self.assertRaises(ValueError):
            run_agent(self.store, EMAIL, mode="live", fault="priority")

    def test_drift_during_notification_requires_review(self):
        apps = DemoApps(self.store)
        original = apps.read_ticket
        reads = []
        def drift(key):
            reads.append(key)
            result = original(key)
            if len(reads) > 1:
                result["priority"] = "Low"
            return result
        apps.read_ticket = drift
        r = run_agent(self.store, EMAIL, apps=apps)
        self.assertEqual(r["state"], "needs_review")

    def test_slack_mentions_escaped(self):
        r = run_agent(self.store, {**EMAIL, "subject": "<!channel> outage"})
        self.assertNotIn("<!channel>", r["notification"])
        self.assertIn("&lt;!channel&gt;", r["notification"])

    @patch("agent.request")
    @patch.dict("os.environ", {"GMAIL_ACCESS_TOKEN": "test-token"})
    def test_gmail_nested_plaintext(self, req):
        req.return_value = {"id": "abc", "payload": {"headers": [{"name": "Subject", "value": "Help"}, {"name": "From", "value": "alex@example.com"}], "parts": [{"mimeType": "multipart/alternative", "parts": [{"mimeType": "text/plain", "body": {"data": "SGVscCBtZQ"}}]}]}}
        self.assertEqual(gmail_message("abc")["body"], "Help me")

    @patch("agent.request")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-token"})
    def test_ai_refusal_blocks_external_creates(self, req):
        req.return_value = {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]}
        r = run_agent(self.store, EMAIL, use_ai=True)
        self.assertEqual(r["state"], "needs_review")
        self.assertNotIn("ticket_id", r)

    @patch("agent.request")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-token"})
    def test_ai_structured_result(self, req):
        req.return_value = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps({"priority": "High", "category": "Technical", "reason": "Production is inaccessible."})}]}]}
        r = run_agent(self.store, EMAIL, use_ai=True)
        self.assertEqual(r["state"], "verified")
        self.assertEqual(r["triage_method"], "OpenAI")


if __name__ == "__main__":
    unittest.main()
