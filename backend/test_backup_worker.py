import os
import unittest
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite://")

import sql_agent  # noqa: E402

MAIN = {"CIMB_INSIGHTS_URL": "https://main.example/insights", "CIMB_INSIGHTS_KEY": "main-key"}
BOTH = {**MAIN, "CIMB_INSIGHTS_BACKUP_URL": "https://backup.example/insights", "CIMB_INSIGHTS_BACKUP_KEY": "backup-key"}


def reply(status, body=None):
    return mock.Mock(status_code=status, json=lambda: body or {})


class BackupWorkerTests(unittest.TestCase):
    def test_backup_is_optional(self):
        with mock.patch.dict(os.environ, MAIN, clear=False):
            os.environ.pop("CIMB_INSIGHTS_BACKUP_URL", None)
            self.assertEqual(sql_agent.worker_endpoints(), [("https://main.example/sql", "main-key")])

    def test_backup_answers_when_main_fails(self):
        calls = []

        def post(url, headers, timeout, json):
            calls.append((url, headers["x-api-key"]))
            return reply(502) if "main" in url else reply(200, {"output": {"ok": True}})

        with mock.patch.dict(os.environ, BOTH), mock.patch("sql_agent.http_requests.post", side_effect=post):
            self.assertEqual(sql_agent.worker_json([{"role": "user", "content": "hi"}], 50), {"ok": True})
        self.assertEqual(calls, [("https://main.example/sql", "main-key"), ("https://backup.example/sql", "backup-key")])

    def test_main_answer_skips_backup(self):
        calls = []

        def post(url, headers, timeout, json):
            calls.append(url)
            return reply(200, {"output": {"ok": True}})

        with mock.patch.dict(os.environ, BOTH), mock.patch("sql_agent.http_requests.post", side_effect=post):
            sql_agent.worker_json([{"role": "user", "content": "hi"}], 50)
        self.assertEqual(calls, ["https://main.example/sql"])

    def test_key_insights_use_backup_when_main_only_fell_back(self):
        import main
        good = {"key_highlights": ["a real one"], "_meta": {"fallback": False}}
        canned = {"key_highlights": ["calculated"], "_meta": {"fallback": True}}

        def post(url, headers, json, timeout):
            return reply(200, canned) if "main" in url else reply(200, good)

        with mock.patch.dict(os.environ, BOTH), mock.patch("main.http_requests.post", side_effect=post):
            self.assertEqual(main._request_cimb_insights({"x": 1}), good)


if __name__ == "__main__":
    unittest.main()
