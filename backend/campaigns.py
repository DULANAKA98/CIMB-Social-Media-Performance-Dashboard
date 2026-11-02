"""
campaigns.py — campaign helpers that do not touch the database or FastAPI.

A post belongs to at most one campaign (posts.campaign holds the campaign name).
Posts join a campaign automatically when their caption contains the campaign
hashtag, or manually when a user supplies the post link.
"""
import re
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import parse_qs, urlparse

# TikTok and YouTube report views as their reach; LinkedIn reports impressions.
# This matches the "Overall" rule used by /api/performance-breakdown.
EXPOSURE_FIELDS = {"TikTok": "views", "YouTube": "views", "LinkedIn": "impressions"}

MAX_IMAGE_CHARS = 3_000_000  # ~2.2 MB of base64; the browser resizes images well below this
IMAGE_PREFIX = re.compile(r"^data:image/(png|jpe?g|webp|gif);base64,[A-Za-z0-9+/=]+$")


def normalize_hashtag(value: Optional[str]) -> str:
    """' #HmmmDulu! ' -> 'HmmmDulu!'. Special characters are kept as typed.

    Returns '' when the value is empty, contains spaces or is over 100 characters.
    """
    tag = str(value or "").strip().lstrip("#")
    return tag if tag and len(tag) <= 100 and not re.search(r"\s", tag) else ""


def caption_has_hashtag(caption: Optional[str], hashtag: str) -> bool:
    """Case-insensitive match of '#' + the hashtag exactly as entered.

    A tag ending in a letter or number must end there in the caption too:
    #hmmmdulu matches '#HmmmDulu!' but not '#hmmmdulu2024'.
    """
    if not hashtag or not caption:
        return False
    boundary = r"(?!\w)" if re.search(r"\w$", hashtag) else ""
    return re.search(rf"#{re.escape(hashtag)}{boundary}", caption, flags=re.IGNORECASE) is not None



def valid_image(value: Optional[str]) -> bool:
    return not value or (len(value) <= MAX_IMAGE_CHARS and IMAGE_PREFIX.match(value) is not None)


def post_link_keys(url: Optional[str]) -> Set[str]:
    """Identifiers that let differently formatted links to the same post match.

    Uses platform post IDs (Instagram shortcode, YouTube video ID, TikTok video ID,
    LinkedIn activity ID, Facebook post/video ID) and ignores www/m. prefixes,
    tracking parameters and trailing slashes.
    """
    raw = str(url or "").strip()
    if not raw:
        return set()
    if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
    except ValueError:
        return set()
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    path = re.sub(r"/+$", "", parsed.path or "")
    query = parse_qs(parsed.query)
    keys = set()

    if "instagram.com" in host:
        match = re.search(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", path)
        if match:
            keys.add(f"ig:{match.group(1)}")
    elif host in ("youtube.com", "youtu.be") or host.endswith(".youtube.com"):
        video = (query.get("v") or [None])[0]
        if not video:
            match = re.search(r"/(?:shorts|embed|live)/([A-Za-z0-9_-]{6,})", path)
            if match:
                video = match.group(1)
        if not video and host == "youtu.be":
            video = path.strip("/").split("/")[0] or None
        if video:
            keys.add(f"yt:{video}")
    elif "tiktok.com" in host:
        match = re.search(r"/(?:video|photo)/(\d+)", path)
        if match:
            keys.add(f"tt:{match.group(1)}")
    elif "linkedin.com" in host:
        match = re.search(r"(?:activity|ugcPost|share)[:-](\d{10,})", raw)
        if match:
            keys.add(f"li:{match.group(1)}")
    elif "facebook.com" in host or host == "fb.watch":
        # Page IDs also appear in links (e.g. ?id= or /<page id>/videos/...), so only
        # the post's own ID is used: the story/video query value or the last path ID.
        for name in ("story_fbid", "fbid", "v"):
            for value in query.get(name, []):
                if re.fullmatch(r"(?:\d{6,}|pfbid\w+)", value):
                    keys.add(f"fb:{value}")
        path_ids = re.findall(r"/(\d{6,}|pfbid\w+)(?=/|$)", path)
        if path_ids:
            keys.add(f"fb:{path_ids[-1]}")
    # No recognised post ID: fall back to the exact host + path + query, so generic
    # paths such as /watch or /permalink.php never match every post.
    if not keys and path:
        keys.add(f"url:{host}{path.lower()}?{parsed.query}")
    return keys


def exposure(row: Dict) -> float:
    field = EXPOSURE_FIELDS.get(row.get("platform"), "reach")
    return float(row.get(field) or 0)


def _mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def summarize(rows: Iterable[Dict]) -> Dict:
    """Totals and organic/paid splits. Avg ER is the mean of post-level ERs."""
    rows = list(rows)
    organic = [row for row in rows if row.get("is_organic") is not False]
    paid = [row for row in rows if row.get("is_organic") is False]

    def totals(group, prefix=""):
        return {
            f"{prefix}posts": len(group),
            f"{prefix}reach": sum(exposure(row) for row in group),
            f"{prefix}views": sum(float(row.get("views") or 0) for row in group),
            f"{prefix}engagement": sum(float(row.get("engagement") or 0) for row in group),
            f"{prefix}avg_er": _mean([float(row.get("engagement_rate") or 0) for row in group]),
        }

    return {**totals(rows), **totals(organic, "organic_"), **totals(paid, "paid_")}
