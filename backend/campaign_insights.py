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
MAX_TOKENS = 1200  # the AI service's maximum; a cut-off reply is unreadable
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


def _f(value) -> str:
    """Number as the reader sees it: thousands commas, at most 2 decimals."""
    if value is None:
        return "n/a"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{int(value):,}"


def _patterns(total, split, platforms, formats, collabs, weekly, top3_share, top_post) -> List[str]:
    """Plain statements of the notable tensions in the numbers, for the model to interpret."""
    out = []
    o, p = split.get("organic") or {}, split.get("paid") or {}
    if o.get("posts") and p.get("posts"):
        out.append(f"Paid posts were {_f(p['posts'])} of {_f(total['posts'])} posts but carried "
                   f"{_f(p.get('share_of_campaign_reach_pct'))}% of reach and {_f(p.get('share_of_campaign_engagement_pct'))}% "
                   f"of engagement. Organic earned {_f(o.get('engagements_per_1000_reach'))} engagements per 1,000 reach vs "
                   f"{_f(p.get('engagements_per_1000_reach'))} for paid; organic ER {_f(o.get('avg_er_pct'))}% vs paid "
                   f"{_f(p.get('avg_er_pct'))}%.")
    if collabs:
        c, own = collabs["collab"], collabs["own"]
        out.append(f"Creator collab posts were {_f(c['posts'])} of {_f(total['posts'])} posts: "
                   f"{_f(c.get('share_of_campaign_reach_pct'))}% of reach but {_f(c.get('share_of_campaign_engagement_pct'))}% "
                   f"of engagement. Collab ER {_f(c.get('avg_er_pct'))}% vs {_f(own.get('avg_er_pct'))}% for own posts "
                   f"({_f(collabs.get('collab_er_vs_own_er_times'))} times).")
    sized = [row for row in platforms if row["posts"] >= 3 and row.get("engagements_per_1000_reach") is not None
             and (row.get("share_of_campaign_reach_pct") or 0) >= 5]
    if len(sized) >= 2:
        best = max(sized, key=lambda row: row["engagements_per_1000_reach"])
        worst = min(sized, key=lambda row: row["engagements_per_1000_reach"])
        out.append(f"{best['name']} earned {_f(best['engagements_per_1000_reach'])} engagements per 1,000 reach "
                   f"({_f(best.get('share_of_campaign_reach_pct'))}% of reach, {_f(best.get('share_of_campaign_engagement_pct'))}% "
                   f"of engagement); {worst['name']} earned {_f(worst['engagements_per_1000_reach'])} "
                   f"({_f(worst.get('share_of_campaign_reach_pct'))}% of reach, {_f(worst.get('share_of_campaign_engagement_pct'))}% "
                   f"of engagement).")
    rated = [row for row in formats if row["posts"] >= 3 and row.get("avg_er_pct") is not None]
    if len(rated) >= 2:
        best = max(rated, key=lambda row: row["avg_er_pct"])
        worst = min(rated, key=lambda row: row["avg_er_pct"])
        out.append(f"Best format by ER: {best['name']} at {_f(best['avg_er_pct'])}% over {_f(best['posts'])} posts, "
                   f"{_f(best['reach_per_post'])} reach per post. Weakest: {worst['name']} at {_f(worst['avg_er_pct'])}% over "
                   f"{_f(worst['posts'])} posts, {_f(worst['reach_per_post'])} reach per post.")
    if top3_share is not None and top_post:
        out.append(f"The top 3 posts delivered {_f(top3_share)}% of all reach. The biggest was a "
                   f"{'paid' if top_post['paid'] else 'organic'} {top_post['platform']} {top_post['format']} on "
                   f"{top_post['date']} with {_f(top_post['reach'])} reach and {_f(top_post['er_pct'])}% ER.")
    if len(weekly) >= 3:
        peak = max(weekly, key=lambda row: row["reach"])
        busiest = max(weekly, key=lambda row: row["posts"])
        best_er = max((row for row in weekly if row["posts"] >= 3), key=lambda row: row.get("avg_er_pct") or 0, default=None)
        text = (f"Peak reach week started {peak['week_starting']}: {_f(peak['posts'])} posts, "
                f"{_f(peak.get('share_of_campaign_reach_pct'))}% of campaign reach. Busiest week started "
                f"{busiest['week_starting']} with {_f(busiest['posts'])} posts and "
                f"{_f(busiest.get('share_of_campaign_reach_pct'))}% of reach.")
        if best_er:
            text += f" Highest ER week (3+ posts) started {best_er['week_starting']} at {_f(best_er.get('avg_er_pct'))}%."
        out.append(text)
    stories = next((row for row in platforms if row["name"] == "Instagram Stories"), None)
    if stories and total["posts"]:
        out.append(f"Instagram Stories were {_f(stories['posts'])} of {_f(total['posts'])} posts but "
                   f"{_f(stories.get('share_of_campaign_reach_pct'))}% of reach, {_f(stories['reach_per_post'])} reach per story.")
    return out


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

    platforms = by(lambda r: r["platform"])
    formats = by(lambda r: f"{r['platform']} {r.get('format') or ''}".strip())
    totals = {**_group(records, total_reach, total_eng), "views": int(sum(_num(r.get("views")) for r in records)),
              "median_post_er_pct": round(median_er, 2)}
    return {
        "campaign": campaign_name,
        "patterns_to_interpret": _patterns(totals, split, platforms, formats, collabs, timeline, top3_share,
                                           _post(by_reach[0]) if by_reach else None),
        "hashtag": f"#{hashtag}" if hashtag else "",
        "period": {"first_post": dates[0] if dates else "", "last_post": dates[-1] if dates else "",
                   "weeks_active": len(weeks)},
        "totals": totals,
        "organic_vs_paid": split,
        "platforms": platforms,
        "formats": formats,
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
    rules = f"""Write exactly 5 points about the campaign "{facts['campaign']}" for its marketing manager, using only the
fact sheet below. "patterns_to_interpret" lists the notable tensions already found in the numbers; build on them.

The manager can already see every total and ratio. A point that only restates numbers is worthless.
Each point must say what the numbers MEAN: the likely reason behind the pattern and its consequence.

Each point has three parts:
- "headline": the takeaway in plain words, at most 70 characters, no numbers. Example: "Paid bought eyeballs, not conversations".
- "text": 2 sentences, 180-300 characters. Sentence 1 gives the evidence: 2-3 numbers that show the contrast.
  Sentence 2 explains what it suggests or why it matters, e.g. "This suggests...", "So...", "The risk is...".
- "kind": "insight" for points 1-3, "decision" for points 4-5.

Insights: pick the 3 most important, different tensions (for example paid vs organic efficiency, creators vs own
posts, platform or format efficiency, a few posts carrying the results, timing and fatigue across weeks).
Decisions: a concrete move for the next wave of this campaign or the next similar one: shift budget from X to Y,
scale or cut a format, change how creators are briefed, change timing, or test something specific. Name what to do,
where, and the number that justifies it. Banned: "keep monitoring", "post consistently", "leverage", "optimize content".

Rules:
- Talk only about this campaign. Never mention content categories or topics.
- Never write "CIMB Malaysia" or "CIMB's"; the reader is CIMB. Do not start with the campaign name.
- Copy every number exactly from the fact sheet, writing thousands with commas (2,581,914). ER values are
  percentages: always add "%". Do not calculate new numbers.
- Plain, confident English. No markdown, no jargon.
- Never put a double quote character inside "headline" or "text"; use single quotes if needed.
- Reply with the JSON object only: no text before or after it, no code fences.

Return JSON: {{"insights": [{{"kind": "insight", "headline": "...", "text": "..."}}, ...]}}

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
        text = _BRAND.sub("", " ".join(str(item.get("text") or "").replace("**", "").split()))
        headline = _BRAND.sub("", " ".join(str(item.get("headline") or "").replace("**", "").split())).rstrip(".")
        text, headline = text[:1].upper() + text[1:], headline[:1].upper() + headline[1:]
        kind = item.get("kind") if item.get("kind") in KINDS else "insight"
        # Too short means it only restated numbers; the prompt asks for evidence plus meaning.
        if len(text) < 110 or len(text) > 420 or len(headline) > 90:
            continue
        if not (_tokens(text) | _tokens(headline)) <= allowed:
            continue
        kept.append({"kind": kind, "headline": headline, "text": text})
    # Insights first, then decisions, as the reader expects.
    kept.sort(key=lambda item: KINDS.index(item["kind"]))
    return kept[:INSIGHT_COUNT]
