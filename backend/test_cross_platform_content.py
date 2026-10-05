import os
import unittest

import pandas as pd

os.environ.setdefault("DATABASE_URL", "sqlite://")

from main import _cross_platform_content_rows  # noqa: E402


class CrossPlatformContentTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame([
            {
                "platform": "Facebook", "title": "Protect yourself from scams! https://cimb.test/fb",
                "link": "https://facebook.test/post", "reach": 100, "views": 120,
                "engagement": 10, "engagement_rate": 10.0,
            },
            {
                "platform": "Instagram", "title": "Protect yourself from scams https://cimb.test/ig",
                "link": "https://instagram.test/post", "reach": 200, "views": 240,
                "engagement": 30, "engagement_rate": 15.0,
            },
            {
                "platform": "YouTube", "title": "Product promotion",
                "link": "https://youtube.test/post", "reach": 300, "views": 300,
                "engagement": 12, "engagement_rate": 4.0,
            },
            {
                "platform": "Instagram Stories", "title": "Protect yourself from scams",
                "link": "https://instagram.test/story", "reach": 50, "views": 60,
                "engagement": 5, "engagement_rate": 10.0,
            },
        ])

    def test_groups_matching_caption_text_across_platforms(self):
        result = _cross_platform_content_rows(self.rows)
        matched = next(row for row in result if row["platform_count"] == 2)

        self.assertEqual(matched["pillar_category"], "Security / Fraud Alert")
        self.assertEqual(matched["post_count"], 2)
        self.assertEqual(matched["platforms"]["Facebook"]["engagement"], 10)
        self.assertEqual(matched["platforms"]["Instagram"]["views"], 240)
        self.assertIsNone(matched["platforms"]["LinkedIn"])
        self.assertEqual(matched["total"]["avg_er"], 12.5)
        self.assertEqual(matched["total"]["reach"], 300)

    def test_excludes_instagram_stories_from_post_comparison(self):
        result = _cross_platform_content_rows(self.rows)
        matched = next(row for row in result if row["platform_count"] == 2)
        self.assertNotIn("Instagram Stories", matched["platforms"])
        self.assertEqual(matched["post_count"], 2)


if __name__ == "__main__":
    unittest.main()
