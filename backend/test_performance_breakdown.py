import os
import unittest

import pandas as pd

os.environ.setdefault("DATABASE_URL", "sqlite://")

from main import _organic_paid_performance_breakdown  # noqa: E402


class PerformanceBreakdownTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame([
            {"platform": "Facebook", "is_organic": True, "reach": 100, "views": 120, "impressions": 0, "engagement": 10, "engagement_rate": 10.0},
            {"platform": "Facebook", "is_organic": False, "reach": 50, "views": 80, "impressions": 0, "engagement": 4, "engagement_rate": 8.0},
            {"platform": "TikTok", "is_organic": True, "reach": 999, "views": 300, "impressions": 0, "engagement": 15, "engagement_rate": 5.0},
            {"platform": "TikTok", "is_organic": False, "reach": 999, "views": 200, "impressions": 0, "engagement": 6, "engagement_rate": 3.0},
            {"platform": "LinkedIn", "is_organic": True, "reach": 999, "views": 25, "impressions": 400, "engagement": 8, "engagement_rate": 2.0},
        ])

    def test_meta_includes_actual_reach_and_separate_views(self):
        result = _organic_paid_performance_breakdown(self.rows)["Facebook"]
        self.assertEqual(result["reach_source"], "reach")
        self.assertTrue(result["include_views"])
        self.assertEqual(result["organic"]["reach"], 100)
        self.assertEqual(result["paid"]["views"], 80)
        self.assertEqual(result["organic"]["average_engagement_rate"], 10)

    def test_tiktok_uses_views_as_reach_proxy(self):
        result = _organic_paid_performance_breakdown(self.rows)["TikTok"]
        self.assertEqual(result["reach_source"], "views")
        self.assertFalse(result["include_views"])
        self.assertEqual(result["organic"]["reach"], 300)
        self.assertEqual(result["paid"]["reach"], 200)

    def test_linkedin_uses_impressions_and_preserves_missing_paid_er(self):
        result = _organic_paid_performance_breakdown(self.rows)["LinkedIn"]
        self.assertEqual(result["reach_source"], "impressions")
        self.assertEqual(result["organic"]["reach"], 400)
        self.assertEqual(result["paid"]["posts"], 0)
        self.assertIsNone(result["paid"]["average_engagement_rate"])

    def test_overall_combines_native_exposure_engagement_and_average_er(self):
        result = _organic_paid_performance_breakdown(self.rows)["Overall"]
        self.assertEqual(result["reach_source"], "mixed")
        self.assertFalse(result["include_views"])
        self.assertEqual(result["organic"]["reach"], 800)
        self.assertEqual(result["paid"]["reach"], 250)
        self.assertEqual(result["organic"]["engagement"], 33)
        self.assertEqual(result["paid"]["engagement"], 10)
        self.assertAlmostEqual(result["organic"]["average_engagement_rate"], 17 / 3)
        self.assertEqual(result["paid"]["average_engagement_rate"], 5.5)


if __name__ == "__main__":
    unittest.main()
