import os
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite://")

from main import get_executive_summary  # noqa: E402


class AiInsightsScopeTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame([
            {
                "platform": "Instagram", "format": "IG reel", "date": pd.Timestamp("2026-07-02"),
                "title": "Instagram launch", "reach": 1000, "engagement": 100,
                "engagement_rate": 10.0,
            },
            {
                "platform": "Facebook", "format": "FB image", "date": pd.Timestamp("2026-07-03"),
                "title": "Facebook launch", "reach": 2000, "engagement": 120,
                "engagement_rate": 6.0,
            },
        ])

    @patch.dict(os.environ, {
        "CIMB_INSIGHTS_URL": "https://example.com/insights/cimb",
        "CIMB_INSIGHTS_KEY": "test-key",
    })
    @patch("main.http_requests.post")
    @patch("main.get_filtered_data")
    def test_selected_platform_is_the_only_data_sent_to_ai(self, filtered_data, post):
        filtered_data.return_value = self.rows
        response = Mock(status_code=200)
        response.json.return_value = {"key_highlights": ["Instagram scoped insight"]}
        post.return_value = response

        result = get_executive_summary("2026-07-01", "2026-07-31", "Instagram")

        self.assertEqual(result["key_highlights"], ["Instagram scoped insight"])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["platform_scope"], "Instagram")
        self.assertEqual(payload["date_range"], {"start": "2026-07-01", "end": "2026-07-31"})
        self.assertEqual([row["name"] for row in payload["platforms"]], ["Instagram"])
        self.assertEqual([row["name"] for row in payload["top_formats"]], ["IG reel"])

    @patch.dict(os.environ, {
        "CIMB_INSIGHTS_URL": "https://example.com/insights/cimb",
        "CIMB_INSIGHTS_KEY": "test-key",
    })
    @patch("main.get_filtered_data")
    def test_unknown_platform_is_rejected(self, filtered_data):
        filtered_data.return_value = self.rows
        with self.assertRaises(HTTPException) as raised:
            get_executive_summary("2026-07-01", "2026-07-31", "Other")
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
