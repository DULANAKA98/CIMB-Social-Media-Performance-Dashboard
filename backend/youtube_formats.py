"""
youtube_formats.py — tell YouTube Shorts from regular videos.

YouTube exports do not say which items are Shorts, and duration is not reliable
(short horizontal videos are regular videos). YouTube itself decides: a Short
stays on youtube.com/shorts/<id> (HTTP 200), while a regular video is redirected
to /watch. Each video is checked once and the answer kept in youtube_formats.
"""
import http.client
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Iterable, Optional

from database import Post, SessionLocal, YoutubeFormat

VIDEO_ID = re.compile(r"[?&]v=\s*([A-Za-z0-9_-]{6,})")


def video_id(link: Optional[str]) -> Optional[str]:
    match = VIDEO_ID.search(str(link or "").replace("%20", ""))
    return match.group(1) if match else None


def check_format(vid: str, attempts: int = 3) -> Optional[str]:
    """'Shorts', 'Video', or None when YouTube gives no clear answer (try again later)."""
    for attempt in range(attempts):
        try:
            conn = http.client.HTTPSConnection("www.youtube.com", timeout=15)
            conn.request("HEAD", f"/shorts/{vid}", headers={"User-Agent": "Mozilla/5.0"})
            response = conn.getresponse()
            location = response.getheader("Location") or ""
            conn.close()
            if response.status == 200:
                return "Shorts"
            if response.status in (301, 302, 303, 307, 308) and "/watch" in location:
                return "Video"
        except OSError:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def known_formats(db, vids: Iterable[str]) -> Dict[str, str]:
    vids = [v for v in set(vids) if v]
    if not vids:
        return {}
    return {row.video_id: row.format for row in db.query(YoutubeFormat).filter(YoutubeFormat.video_id.in_(vids))}


def apply_known_formats(db, records):
    """Give uploaded YouTube records their saved format so a re-upload never resets it to Video."""
    youtube = [r for r in records if r.get("platform") == "YouTube"]
    saved = known_formats(db, (video_id(r.get("link")) for r in youtube))
    for record in youtube:
        record["format"] = saved.get(video_id(record.get("link")), record.get("format") or "Video")


def classify_pending(checker=check_format, workers: int = 6) -> Dict[str, int]:
    """Check every YouTube post whose video has no saved format yet; runs after an upload."""
    db = SessionLocal()
    try:
        posts = db.query(Post).filter(Post.platform == "YouTube").all()
        by_video: Dict[str, list] = {}
        for post in posts:
            vid = video_id(post.link)
            if vid:
                by_video.setdefault(vid, []).append(post)
        saved = known_formats(db, by_video)
        pending = [vid for vid in by_video if vid not in saved]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(zip(pending, pool.map(checker, pending)))
        counts = {"Shorts": 0, "Video": 0, "unresolved": 0}
        for vid, fmt in results.items():
            if not fmt:
                counts["unresolved"] += 1
                continue
            counts[fmt] += 1
            db.merge(YoutubeFormat(video_id=vid, format=fmt, checked_at=datetime.utcnow()))
            for post in by_video[vid]:
                post.format = fmt
        db.commit()
        print(f"YouTube format check: {counts}")
        return counts
    finally:
        db.close()
