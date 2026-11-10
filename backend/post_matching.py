"""
post_matching.py — keep re-uploaded Facebook posts on their existing rows.

Post IDs come from the link, but Facebook can give the same post a different
pfbid link in a later export, which would add a duplicate. Before saving, each
uploaded Facebook record is pointed at the existing row for the same post:
  1. same Meta Post ID (stored in posts.external_id),
  2. otherwise the same link (the record's own id, as before),
  3. otherwise, for rows saved before Post IDs were stored, the only Facebook
     post with the same date and caption.
"""
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from campaigns import post_link_keys
from database import Post


def resolve_by_link(db, records: List[Dict]) -> int:
    """Point records at an existing post with the same link but a different id.

    Rows added by hand in Data Hub get a random id, while uploads derive ids from
    the link; without this, uploading that post later would add a second row.
    """
    platforms = {r.get("platform") for r in records if r.get("link")}
    if not platforms:
        return 0
    existing = db.query(Post.id, Post.platform, Post.link).filter(Post.platform.in_(platforms), Post.link.isnot(None)).all()
    known_ids = {row.id for row in existing}
    by_key = defaultdict(set)
    for row in existing:
        for key in post_link_keys(row.link):
            by_key[(row.platform, key)].add(row.id)
    redirected = 0
    for record in records:
        if record["id"] in known_ids:
            continue
        matches = set().union(*[by_key.get((record.get("platform"), k), set()) for k in post_link_keys(record.get("link"))] or [set()])
        if len(matches) == 1:
            record["id"] = matches.pop()
            redirected += 1
    return redirected


def _caption_key(title) -> str:
    return " ".join(str(title or "").split())[:80].lower()


def _day(value):
    if not value:
        return None
    try:
        return (value if isinstance(value, datetime) else datetime.fromisoformat(str(value))).date()
    except ValueError:
        return None


def resolve_facebook_ids(db, records: List[Dict]) -> int:
    """Rewrite record ids to existing rows of the same post. Returns how many were redirected."""
    facebook = [r for r in records if r.get("platform") == "Facebook"]
    if not facebook:
        return 0
    existing = db.query(Post.id, Post.external_id, Post.date, Post.title).filter(Post.platform == "Facebook").all()
    by_external = {row.external_id: row.id for row in existing if row.external_id}
    known_ids = {row.id for row in existing}
    by_caption = defaultdict(list)
    for row in existing:
        if not row.external_id and row.title and row.date:
            by_caption[(row.date.date(), _caption_key(row.title))].append(row.id)

    redirected, claimed = 0, set()
    for record in facebook:
        external = record.get("external_id")
        target = None
        if external and external in by_external:
            target = by_external[external]
        elif record["id"] in known_ids:
            target = record["id"]
        else:
            candidates = [i for i in by_caption.get((_day(record.get("date")), _caption_key(record.get("title"))), [])
                          if i not in claimed]
            if len(candidates) == 1:
                target = candidates[0]
        if target:
            claimed.add(target)
            if target != record["id"]:
                record["id"] = target
                redirected += 1
    return redirected
