import os
import tempfile
import unittest
from datetime import datetime

_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'yt_formats_test.db')}"

import youtube_formats as yf  # noqa: E402
from database import Base, Post, SessionLocal, YoutubeFormat, engine  # noqa: E402
from main import app  # noqa: E402


def _yt(post_id, vid):
    return Post(id=post_id, platform="YouTube", format="Video", title=post_id,
                link=f"https://youtube.com/watch?v={vid}", date=datetime(2026, 10, 1))


class YoutubeFormatTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        db.add_all([_yt("a", "shortAAA111"), _yt("b", "videoBBB222"), _yt("c", "flakyCCC333")])
        db.commit()
        db.close()

    def test_video_id_handles_studio_space_and_short_links(self):
        self.assertEqual(yf.video_id("https://youtube.com/watch?v= -BK_gZmn7IY"), "-BK_gZmn7IY")
        self.assertEqual(yf.video_id("https://youtube.com/watch?v=%20-BK_gZmn7IY"), "-BK_gZmn7IY")
        self.assertIsNone(yf.video_id("https://youtube.com/channel/abc"))

    def test_background_check_labels_posts_and_remembers(self):
        answers = {"shortAAA111": "Shorts", "videoBBB222": "Video", "flakyCCC333": None}
        calls = []

        def fake_checker(vid):
            calls.append(vid)
            return answers[vid]

        counts = yf.classify_pending(checker=fake_checker, workers=2)
        self.assertEqual(counts, {"Shorts": 1, "Video": 1, "unresolved": 1})
        db = SessionLocal()
        self.assertEqual({p.id: p.format for p in db.query(Post)}, {"a": "Shorts", "b": "Video", "c": "Video"})
        self.assertEqual(db.query(YoutubeFormat).count(), 2)  # the unresolved one is retried next time
        db.close()

        calls.clear()
        yf.classify_pending(checker=fake_checker, workers=2)
        self.assertEqual(calls, ["flakyCCC333"])  # saved answers are not checked again

    def test_reupload_keeps_saved_format(self):
        db = SessionLocal()
        db.add(YoutubeFormat(video_id="shortAAA111", format="Shorts"))
        db.commit()
        records = [{"platform": "YouTube", "format": "Video", "link": "https://youtube.com/watch?v=shortAAA111"},
                   {"platform": "YouTube", "format": "Video", "link": "https://youtube.com/watch?v=newDDD444"},
                   {"platform": "TikTok", "format": "Video", "link": "https://tiktok.com/x"}]
        yf.apply_known_formats(db, records)
        db.close()
        self.assertEqual([r["format"] for r in records], ["Shorts", "Video", "Video"])

    def test_upload_endpoint_receives_background_tasks(self):
        route = next(r for r in app.routes if getattr(r, "path", "") == "/api/upload-platform-files")
        self.assertEqual(route.dependant.background_tasks_param_name, "background_tasks")


if __name__ == "__main__":
    unittest.main()
