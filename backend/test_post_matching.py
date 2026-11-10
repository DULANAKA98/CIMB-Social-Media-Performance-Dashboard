import os
import tempfile
import unittest
from datetime import datetime

_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'matching_test.db')}"

import pandas as pd  # noqa: E402

from data_processor import process_data  # noqa: E402
from database import Base, Post, SessionLocal, engine  # noqa: E402
from post_matching import resolve_by_link, resolve_facebook_ids  # noqa: E402

CAPTION = "Consider this your mission briefing. 🫡 🎁\nHere’s how you can join Mission Happiness"


def record(rid, link, external=None, caption=CAPTION, day="2026-09-18T12:00:00"):
    return {"id": rid, "platform": "Facebook", "link": link, "external_id": external, "title": caption, "date": day}


class FacebookMatchingTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        db.add(Post(id="fb_old", platform="Facebook", link="https://www.facebook.com/CIMBMalaysia/posts/pfbidOLD",
                    title=CAPTION.replace("\n", "\r\n"), date=datetime(2026, 9, 18, 9, 0), campaign="OctoFest"))
        db.add(Post(id="fb_other", platform="Facebook", link="https://www.facebook.com/x/posts/pfbidZZZ",
                    title="A different post", date=datetime(2026, 9, 18, 15, 0)))
        db.commit()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_changed_link_falls_back_to_date_and_caption(self):
        records = [record("fb_new_link", "https://www.facebook.com/CIMBMalaysia/posts/pfbidNEW", external="111_222")]
        self.assertEqual(resolve_facebook_ids(self.db, records), 1)
        self.assertEqual(records[0]["id"], "fb_old")

    def test_stored_post_id_wins_even_if_caption_and_link_change(self):
        self.db.query(Post).filter(Post.id == "fb_old").update({Post.external_id: "111_222"})
        self.db.commit()
        records = [record("fb_newer", "https://www.facebook.com/p/pfbidNEWER", external="111_222", caption="Edited caption")]
        resolve_facebook_ids(self.db, records)
        self.assertEqual(records[0]["id"], "fb_old")

    def test_same_link_keeps_its_own_id_and_new_posts_stay_new(self):
        records = [record("fb_old", "https://www.facebook.com/CIMBMalaysia/posts/pfbidOLD"),
                   record("fb_brand_new", "https://www.facebook.com/p/pfbidX", caption="Brand new post", day="2026-11-01T10:00:00")]
        self.assertEqual(resolve_facebook_ids(self.db, records), 0)
        self.assertEqual([r["id"] for r in records], ["fb_old", "fb_brand_new"])

    def test_ambiguous_caption_is_not_guessed(self):
        self.db.add(Post(id="fb_twin", platform="Facebook", link="https://www.facebook.com/p/pfbidTWIN",
                         title=CAPTION, date=datetime(2026, 9, 18, 20, 0)))
        self.db.commit()
        records = [record("fb_new_link", "https://www.facebook.com/p/pfbidNEW")]
        self.assertEqual(resolve_facebook_ids(self.db, records), 0)
        self.assertEqual(records[0]["id"], "fb_new_link")

    def test_hand_added_post_is_updated_by_a_later_upload(self):
        self.db.add(Post(id="2d984b69-manual", platform="TikTok", link="https://www.tiktok.com/@cimbmalaysia/video/7704532093979626759",
                         title="Typed in Data Hub", date=datetime(2026, 11, 5)))
        self.db.commit()
        records = [{"id": "tt_hash_of_link", "platform": "TikTok", "title": "From export",
                    "link": "https://www.tiktok.com/@cimbmalaysia/video/7704532093979626759?is_from_webapp=1"},
                   {"id": "tt_brand_new", "platform": "TikTok", "link": "https://www.tiktok.com/@cimbmalaysia/video/7700000000000000009"}]
        self.assertEqual(resolve_by_link(self.db, records), 1)
        self.assertEqual([r["id"] for r in records], ["2d984b69-manual", "tt_brand_new"])

    def test_facebook_upload_reads_post_id(self):
        empty = pd.DataFrame()
        frame = pd.DataFrame([{"Post ID": "1141555928596207_987654321", "Publish time": "09/18/2026 10:00",
                               "Permalink": "https://www.facebook.com/x/posts/pfbidA", "Viewers": "10", "Views": "20",
                               "Reactions, comments and shares": "3", "Comments": "1", "Shares": "1"}])
        rec = process_data(frame, empty, empty, empty, empty, ig_story=empty)[0]
        self.assertEqual(rec["external_id"], "1141555928596207_987654321")


if __name__ == "__main__":
    unittest.main()
