"""Strategic AI insights for one campaign.

The backend works out a fact sheet from the campaign's own posts (splits, shares,
ratios, timeline, standout posts), so the model can point at what the numbers mean
without doing arithmetic. Every number in a returned insight must appear in that
fact sheet; anything else is dropped.
"""
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import campaigns as helpers

INSIGHT_COUNT = 5
KINDS = ("insight", "decision")


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _avg(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 2) if values else None


def _pct(part: float, whole: float) -> Optional[float]:
    return round(100 * part / whole, 1) if whole else None


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return round(a / b, 1) if a and b else None


def _group(records: List[Dict[str, Any]], total_reach: float, total_eng: float) -> Dict[str, Any]:
    reach = sum(helpers.exposure(r) for r in records)
    eng = sum(_num(r.get("engagement")) for r in records)
    row = {
        "posts": len(records),
        "reach": int(reach),
        "engagement": int(eng),
        "avg_er_pct": _avg([_num(r.get("engagement_rate")) for r in records]),
        "share_of_campaign_reach_pct": _pct(reach, total_reach),
        "share_of_campaign_engagement_pct": _pct(eng, total_eng),
        "reach_per_post": int(reach / len(records)) if records else 0,
        "engagements_per_1000_reach": round(1000 * eng / reach, 1) if reach else None,
    }
    return {k: v for k, v in row.items() if v is not None}


def _label(r: Dict[str, Any]) -> str:
    title = " ".join(str(r.get("title") or "").split())
    return (title[:70] + "…") if len(title) > 70 else (title or "Untitled post")


def _post(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "post": _label(r), "platform": r["platform"], "format": r.get("format") or "",
        "date": (r.get("date") or "")[:10], "paid": r.get("is_organic") is False,
        "collab": r.get("collab") or None,
        "reach": int(helpers.exposure(r)), "engagement": int(_num(r.get("engagement"))),
        "er_pct": round(_num(r.get("engagement_rate")), 2),
    }


def _week_start(value: str) -> Optional[date]:
    try:
        day = datetime.fromisoformat(value[:10]).date()
    except (TypeError, ValueError):
        return None
    return day - timedelta(days=day.weekday())


def build_facts(campaign_name: str, hashtag: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_reach = sum(helpers.exposure(r) for r in records)
    total_eng = sum(_num(r.get("engagement")) for r in records)
    dates = sorted(r["date"][:10] for r in records if r.get("date"))

    organic = [r for r in records if r.get("is_organic") is not False]
    paid = [r for r in records if r.get("is_organic") is False]
    split = {"organic": _group(organic, total_reach, total_eng), "paid": _group(paid, total_reach, total_eng)}
    if organic and paid:
        o, p = split["organic"], split["paid"]
        split["organic_er_vs_paid_er_times"] = _ratio(o.get("avg_er_pct"), p.get("avg_er_pct"))
        split["organic_engagements_per_1000_reach_vs_paid_times"] = _ratio(o.get("engagements_per_1000_reach"),
                                                                           p.get("engagements_per_1000_reach"))
        split["paid_reach_per_post_vs_organic_times"] = _ratio(p.get("reach_per_post"), o.get("reach_per_post"))

    def by(key_fn) -> List[Dict[str, Any]]:
        buckets = defaultdict(list)
        for r in records:
            key = key_fn(r)
            if key:
                buckets[key].append(r)
        rows = [{"name": k, **_group(v, total_reach, total_eng)} for k, v in buckets.items()]
        return sorted(rows, key=lambda row: row["reach"], reverse=True)

    collab = [r for r in records if (r.get("collab") or "").strip()]
    own = [r for r in records if not (r.get("collab") or "").strip()]
    collabs = None
    if collab:
        collabs = {"collab": _group(collab, total_reach, total_eng), "own": _group(own, total_reach, total_eng)}
        collabs["collab_er_vs_own_er_times"] = _ratio(collabs["collab"].get("avg_er_pct"), collabs["own"].get("avg_er_pct"))

    weeks = defaultdict(list)
    for r in records:
        start = _week_start(r.get("date") or "")
        if start:
            weeks[start].append(r)
    timeline = [{"week_starting": str(k), **{key: val for key, val in _group(v, total_reach, total_eng).items()
                                              if key in ("posts", "reach", "engagement", "avg_er_pct",
                                                         "share_of_campaign_reach_pct")}}
                for k, v in sorted(weeks.items())][:12]

    by_reach = sorted(records, key=helpers.exposure, reverse=True)
    top3_share = _pct(sum(helpers.exposure(r) for r in by_reach[:3]), total_reach)
    # ER is only meaningful for posts that reached a reasonable audience.
    reach_floor = sorted(helpers.exposure(r) for r in records)[len(records) // 4] if records else 0
    rated = [r for r in records if helpers.exposure(r) >= reach_floor and helpers.exposure(r) > 0]
    by_er = sorted(rated, key=lambda r: _num(r.get("engagement_rate")), reverse=True)
    median_er = sorted(_num(r.get("engagement_rate")) for r in records)[len(records) // 2] if records else 0

    return {
        "campaign": campaign_name,
        "hashtag": f"#{hashtag}" if hashtag else "",
        "period": {"first_post": dates[0] if dates else "", "last_post": dates[-1] if dates else "",
                   "weeks_active": len(weeks)},
        "totals": {**_group(records, total_reach, total_eng), "views": int(sum(_num(r.get("views")) for r in records)),
                   "median_post_er_pct": round(median_er, 2)},
        "organic_vs_paid": split,
        "platforms": by(lambda r: r["platform"]),
        "formats": by(lambda r: f"{r['platform']} {r.get('format') or ''}".strip()),
        "creator_collabs_vs_own_posts": collabs,
        "weekly": timeline,
        "concentration": {"top_3_posts_share_of_reach_pct": top3_share,
                          "posts_above_median_er": sum(1 for r in records if _num(r.get("engagement_rate")) > median_er)},
        "top_posts_by_reach": [_post(r) for r in by_reach[:4]],
        "top_posts_by_er": [_post(r) for r in by_er[:4]],
        "weakest_posts_by_er": [_post(r) for r in by_er[-3:]] if len(by_er) > 7 else [],
        "notes": [
            "Reach = reported reach, except TikTok and YouTube use views and LinkedIn uses impressions.",
            "ER values are percentages: the average of post-level engagement rates.",
            "Paid reach comes from boosted or advertised posts, so it buys exposure rather than earning it.",
        ],
    }


SYSTEM = (
    "You are a senior social media strategist on the CIMB in-house team, reviewing one campaign for the "
    "marketing manager. You find what the numbers mean, not what they say. Return only JSON."
)


def build_messages(facts: Dict[str, Any]) -> List[Dict[str, str]]:
    rules = f"""Write exactly 5 points about the campaign "{facts['campaign']}" using only the fact sheet below.

- Points 1-3, kind "insight": a hidden pattern or tension in the numbers and why it matters. Compare things
  (organic vs paid, platform vs platform, format vs format, early weeks vs later weeks, collabs vs own posts,
  a few posts carrying the reach). Never just restate a total; the reader can already see the totals.
- Points 4-5, kind "decision": a specific, practical decision for the next wave of this campaign or the next
  similar campaign: what to do more of, cut, move budget to or from, test, or brief differently, and the
  number that justifies it. No generic advice like "keep monitoring" or "post consistently".
- Talk only about this campaign. Never mention content categories, topics or anything outside the fact sheet.
- Never write "CIMB Malaysia" or "CIMB's"; the reader is CIMB. Do not start with the campaign name.
- Every number you write must be copied exactly from the fact sheet. ER values are percentages: write them
  with "%". Do not calculate new numbers; ratios, shares and per-post figures are already provided.
- Each point is one or two short sentences, at most 230 characters. Plain words, no jargon, no markdown.

Return JSON: {{"insights": [{{"kind": "insight", "text": "..."}}, ...]}}

Fact sheet: {json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": rules}]


_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _tokens(value: Any) -> set:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    out = set()
    for token in _NUMBER.findall(text):
        token = token.replace(",", "")
        if "." in token:
            token = token.rstrip("0").rstrip(".")
        out.add(token)
    return out


_BRAND = re.compile(r"\bCIMB(?:\s+Malaysia)?(?:'s|’s)?\s+", re.IGNORECASE)


def clean_and_ground(output: Any, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    """Keep well-formed points whose numbers all appear in the fact sheet."""
    allowed = _tokens(facts) | {str(n) for n in range(0, 11)}
    items = output.get("insights") if isinstance(output, dict) else None
    kept = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").replace("**", "").split())
        text = _BRAND.sub("", text)
        text = text[:1].upper() + text[1:]
        kind = item.get("kind") if item.get("kind") in KINDS else "insight"
        if len(text) < 20 or len(text) > 320:
            continue
        if not _tokens(text) <= allowed:
            continue
        kept.append({"kind": kind, "text": text})
    # Insights first, then decisions, as the reader expects.
    kept.sort(key=lambda item: KINDS.index(item["kind"]))
    return kept[:INSIGHT_COUNT]
