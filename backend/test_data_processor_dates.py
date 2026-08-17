import unittest

import pandas as pd

from data_processor import parse_platform_dates


class PlatformDateParsingTests(unittest.TestCase):
    def assert_dates(self, raw_dates, platform, expected_dates):
        parsed = parse_platform_dates(pd.Series(raw_dates), platform)
        self.assertEqual(
            [value.strftime("%Y-%m-%d") for value in parsed],
            expected_dates,
        )

    def test_tiktok_day_first_dates_use_unambiguous_file_evidence(self):
        self.assert_dates(
            ["14/8/2026 10:00", "12/8/2026 12:06", "10/8/2026 9:59"],
            "tiktok",
            ["2026-08-14", "2026-08-12", "2026-08-10"],
        )

    def test_tiktok_ambiguous_only_file_uses_day_first_fallback(self):
        self.assert_dates(
            ["12/8/2026 12:06", "10/8/2026 9:59"],
            "tiktok",
            ["2026-08-12", "2026-08-10"],
        )

    def test_meta_ambiguous_dates_keep_month_first_order(self):
        for platform in ("facebook", "instagram", "instagram_story"):
            with self.subTest(platform=platform):
                self.assert_dates(
                    ["07/12/2026 10:00", "07/08/2026 09:00"],
                    platform,
                    ["2026-07-12", "2026-07-08"],
                )

    def test_youtube_detects_month_first_export_when_file_proves_it(self):
        self.assert_dates(
            ["8/14/2026", "8/10/2026"],
            "youtube",
            ["2026-08-14", "2026-08-10"],
        )

    def test_youtube_ambiguous_only_file_uses_day_first_fallback(self):
        self.assert_dates(
            ["12/8/2026", "10/8/2026"],
            "youtube",
            ["2026-08-12", "2026-08-10"],
        )

    def test_linkedin_month_first_dates_match_native_export(self):
        self.assert_dates(
            ["06/30/2026", "06/12/2026", "06/08/2026"],
            "linkedin",
            ["2026-06-30", "2026-06-12", "2026-06-08"],
        )

    def test_iso_dates_are_not_reordered(self):
        self.assert_dates(
            ["2026-08-10T09:59:00", "2026-12-08"],
            "tiktok",
            ["2026-08-10", "2026-12-08"],
        )


if __name__ == "__main__":
    unittest.main()
