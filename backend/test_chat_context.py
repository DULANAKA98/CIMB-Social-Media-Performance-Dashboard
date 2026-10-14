import os
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("DATABASE_URL", "sqlite://")

from main import _cimb_chat_context  # noqa: E402


class ChatContextTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame([
            {
                "id": "ig-1", "platform": "Instagram", "format": "Reel", "date": pd.Timestamp("2026-07-02"),
                "title": "Product launch", "reach": 1000, "views": 1200, "engagement": 100,
                "likes": 80, "comments": 10, "shares": 10, "engagement_rate": 10.0, "is_organic": True,
            },
            {
                "id": "fb-1", "platform": "Facebook", "format": "Image", "date": pd.Timestamp("2026-07-03"),
                "title": "Financial literacy tip", "reach": 2000, "views": 2200, "engagement": 120,
                "likes": 100, "comments": 12, "shares": 8, "engagement_rate": 6.0, "is_organic": True,
            },
        ])

    @patch("main._chat_follower_context", return_value=[])
    def test_context_reconciles_dashboard_totals(self, _followers):
        context = _cimb_chat_context(self.rows, None, None, "executive", None)
        self.assertEqual(context["totals"]["posts"], 2)
        self.assertEqual(context["totals"]["reach"], 3000)
        self.assertEqual(context["totals"]["engagement"], 220)
        self.assertEqual(context["date_range"], {"start": "2026-07-02", "end": "2026-07-03"})
        self.assertEqual(len(context["platforms"]), 2)

    @patch("main._chat_follower_context", return_value=[])
    def test_context_honours_selected_platform(self, _followers):
        context = _cimb_chat_context(self.rows, None, None, "platform", "Instagram")
        self.assertEqual(context["platform_filter"], "Instagram")
        self.assertEqual(context["totals"]["posts"], 1)
        self.assertEqual(context["platforms"][0]["name"], "Instagram")
        self.assertEqual(context["top_posts"][0]["title"], "Product launch")


if __name__ == "__main__":
    unittest.main()
