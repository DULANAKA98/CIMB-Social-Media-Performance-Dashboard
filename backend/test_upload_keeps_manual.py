import os
import re
import unittest

import pandas as pd

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy.dialects import postgresql  # noqa: E402

from data_processor import process_data  # noqa: E402
from main import post_upsert  # noqa: E402

EMPTY = pd.DataFrame()
TIKTOK = {"Video link": "https://www.tiktok.com/@cimbmalaysia/video/7700000000000000001", "Post time": "2026-10-01 10:00",
          "Video title": "A post", "Video views": "1000", "Likes": "10", "Comments": "1", "Shares": "1"}


def tiktok(extra=None):
    return process_data(EMPTY, EMPTY, EMPTY, pd.DataFrame([{**TIKTOK, **(extra or {})}]), EMPTY, ig_story=EMPTY)


def set_clause(rec):
    values = {"id": "tt_1", "platform": "TikTok", "collab": rec.get("collab") or "", "reach": 1.0,
              "is_organic": True if rec.get("is_organic") is None else rec["is_organic"], "external_id": None}
    sql = str(post_upsert(values, rec).compile(dialect=postgresql.dialect()))
    return sql.split("DO UPDATE SET", 1)[1]


class KeepManualFieldsTests(unittest.TestCase):
    def test_file_without_columns_leaves_fields_unset(self):
        records = tiktok()
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["collab"])
        self.assertIsNone(records[0]["is_organic"])

    def test_file_with_columns_still_sets_them(self):
        records = tiktok({"Collab": "Creator X", "Organic/Paid": "Paid"})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["collab"], "Creator X")
        self.assertFalse(records[0]["is_organic"])

    def test_facebook_still_decides_paid_from_meta_data(self):
        frame = pd.DataFrame([{"Publish time": "10/01/2026 10:00", "Permalink": "https://www.facebook.com/x/posts/1",
                               "Viewers": "800", "Views": "1000", "Views from Boosted posts": "500",
                               "Reactions, comments and shares": "5", "Comments": "1", "Shares": "1"}])
        rec = process_data(frame, EMPTY, EMPTY, EMPTY, EMPTY, ig_story=EMPTY)[0]
        self.assertIsNone(rec["collab"])
        self.assertIs(rec["is_organic"], False)

    def test_collab_comes_from_partner_account(self):
        base = {"Publish time": "10/24/2026 10:00", "Description": "x", "Views": "10", "Reach": "8",
                "Likes": "1", "Comments": "0", "Shares": "0", "Saves": "0"}
        frame = pd.DataFrame([{**base, "Permalink": "https://www.instagram.com/p/AAA/", "Account username": "johorfoodie"},
                              {**base, "Permalink": "https://www.instagram.com/p/BBB/", "Account username": "cimbmalaysia"}])
        records = process_data(EMPTY, frame, EMPTY, EMPTY, EMPTY, ig_story=EMPTY)
        self.assertEqual([r["collab"] for r in records], ["johorfoodie", None])  # own post keeps its stored collab

        fb = pd.DataFrame([{"Publish time": "10/29/2026 10:00", "Permalink": "https://www.facebook.com/x/posts/1",
                            "Page name": "Innogen Malaysia", "Viewers": "5", "Views": "9"},
                           {"Publish time": "10/29/2026 11:00", "Permalink": "https://www.facebook.com/x/posts/2",
                            "Page name": "CIMB Malaysia", "Viewers": "5", "Views": "9"}])
        self.assertEqual([r["collab"] for r in process_data(fb, EMPTY, EMPTY, EMPTY, EMPTY, ig_story=EMPTY)],
                         ["Innogen Malaysia", None])

    def test_collab_column_still_wins_over_account(self):
        frame = pd.DataFrame([{"Publish time": "10/24/2026 10:00", "Permalink": "https://www.instagram.com/p/AAA/",
                               "Account username": "johorfoodie", "Collab": "Johor Foodie (KOL)", "Views": "10", "Reach": "8"}])
        self.assertEqual(process_data(EMPTY, frame, EMPTY, EMPTY, EMPTY, ig_story=EMPTY)[0]["collab"], "Johor Foodie (KOL)")

    def test_upsert_skips_fields_the_file_did_not_provide(self):
        kept = set_clause({"collab": None, "is_organic": None})
        self.assertNotRegex(kept, r"\bcollab\s*=")
        self.assertNotRegex(kept, r"\bis_organic\s*=")
        self.assertRegex(kept, r"\breach\s*=")

    def test_upsert_writes_fields_the_file_provided(self):
        written = set_clause({"collab": "Creator X", "is_organic": False})
        self.assertRegex(written, r"\bcollab\s*=")
        self.assertRegex(written, r"\bis_organic\s*=")


if __name__ == "__main__":
    unittest.main()
