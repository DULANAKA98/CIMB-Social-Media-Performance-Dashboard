from fastapi import FastAPI, Query, HTTPException, Response, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from data_processor import calculate_fb_ig_engagement_rate, process_data
from database import init_db, get_db, Post, AiReport
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import pandas as pd
import math
import json
import os
import io
import requests as http_requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  # Load GROQ_API_KEY and DATABASE_URL from .env

app = FastAPI(title="Social Media Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize database tables on startup ─────────────────────────────────────
@app.on_event("startup")
def startup_event():
    try:
        init_db()
    except Exception as e:
        print(f"DB init warning: {e}")


# ── Helper: load posts from DB into a Pandas DataFrame ────────────────────────
INSTAGRAM_STORY_FORMATS = ('ig story', 'instagram story', 'story')


def is_instagram_story(platform, content_format) -> bool:
    return (
        str(platform or '').strip().lower() == 'instagram'
        and str(content_format or '').strip().lower() in INSTAGRAM_STORY_FORMATS
    )


def effective_engagement_rate(platform, content_format, engagement, reach, views, stored_rate=0):
    """Return the authoritative per-post ER shown throughout the tool."""
    normalized_platform = str(platform or '').strip().lower()
    if normalized_platform in ('facebook', 'instagram') and not is_instagram_story(platform, content_format):
        return calculate_fb_ig_engagement_rate(
            float(engagement or 0), float(reach or 0), float(views or 0)
        )
    return float(stored_rate or 0)


def without_instagram_stories(query):
    """Exclude Instagram Story rows from every analytics query."""
    platform = func.lower(func.trim(func.coalesce(Post.platform, '')))
    content_format = func.lower(func.trim(func.coalesce(Post.format, '')))
    return query.filter(~((platform == 'instagram') & content_format.in_(INSTAGRAM_STORY_FORMATS)))


def exclude_instagram_stories_from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Exclude Instagram Stories from legacy sheet-backed analytics paths."""
    if df.empty or 'Platform' not in df.columns or 'Format' not in df.columns:
        return df
    platform = df['Platform'].fillna('').astype(str).str.strip().str.lower()
    content_format = df['Format'].fillna('').astype(str).str.strip().str.lower()
    return df[~((platform == 'instagram') & content_format.isin(INSTAGRAM_STORY_FORMATS))].copy()


def get_filtered_data(start_date: Optional[str] = None, end_date: Optional[str] = None):
    db = next(get_db())
    try:
        query = without_instagram_stories(db.query(Post))
        if start_date:
            query = query.filter(Post.date >= pd.to_datetime(start_date))
        if end_date:
            end_dt = pd.to_datetime(end_date)
            if end_dt.time() == pd.Timestamp('00:00:00').time():
                end_dt = end_dt + pd.Timedelta(days=1, seconds=-1)
            query = query.filter(Post.date <= end_dt)
        rows = query.all()
        if not rows:
            raise HTTPException(status_code=400, detail="No data in database. Please upload platform Excel files first.")
        records = []
        for r in rows:
            records.append({
                'id': r.id, 'platform': r.platform, 'format': r.format,
                'collab': getattr(r, 'collab', '') or '',
                'date': r.date, 'title': r.title, 'link': r.link,
                'reach': r.reach or 0, 'views': r.views or 0,
                'engagement': r.engagement or 0, 'likes': r.likes or 0,
                'comments': r.comments or 0, 'shares': r.shares or 0,
                'favorites': r.favorites or 0, 'reposts': r.reposts or 0,
                'impressions': getattr(r, 'impressions', 0) or 0,
                'watch_time_hours': getattr(r, 'watch_time_hours', 0) or 0,
                'engagement_rate': effective_engagement_rate(
                    r.platform, r.format, r.engagement, r.reach, r.views, r.engagement_rate
                ),
                'is_organic': r.is_organic,
            })
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])

        return df
    finally:
        db.close()


# ── Status endpoint — lets frontend know if DB has data ───────────────────────
@app.get("/api/status")
def get_status():
    db = next(get_db())
    try:
        count = without_instagram_stories(db.query(Post)).count()
        last_post = db.query(Post).order_by(Post.created_at.desc()).first()
        last_sync = last_post.created_at.isoformat() if last_post else None
        return {"has_data": count > 0, "post_count": count, "last_sync": last_sync}
    except Exception as e:
        return {"has_data": False, "post_count": 0, "last_sync": None, "error": str(e)}
    finally:
        db.close()


# ── Upload platform Excel files → DB (upsert, never delete) ──────────────────
PLATFORM_UPLOADS = {
    "fb": {"sheet": "Raw_FB", "label": "Facebook"},
    "ig": {"sheet": "Raw_IG", "label": "Instagram"},
    "ig_story": {"sheet": "Raw_IG_Story", "label": "Instagram Stories"},
    "tt": {"sheet": "Raw_Tiktok", "label": "TikTok"},
    "yt": {"sheet": "Raw_Youtube", "label": "YouTube"},
    "li": {"sheet": "Raw_LI", "label": "LinkedIn"},
}


def _read_platform_file(contents: bytes, filename: str, expected_sheet: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(contents), dtype=str)

    xl = pd.ExcelFile(io.BytesIO(contents))
    if not xl.sheet_names:
        raise ValueError("The workbook does not contain any worksheets.")
    sheet_name = expected_sheet if expected_sheet in xl.sheet_names else xl.sheet_names[0]
    return xl.parse(sheet_name, dtype=str)


@app.post("/api/upload-platform-files")
async def upload_platform_files(
    fb_file: Optional[UploadFile] = File(None),
    ig_file: Optional[UploadFile] = File(None),
    ig_story_file: Optional[UploadFile] = File(None),
    tt_file: Optional[UploadFile] = File(None),
    yt_file: Optional[UploadFile] = File(None),
    li_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    uploads = {
        "fb": fb_file,
        "ig": ig_file,
        "ig_story": ig_story_file,
        "tt": tt_file,
        "yt": yt_file,
        "li": li_file,
    }
    selected_uploads = {key: upload for key, upload in uploads.items() if upload is not None}
    if not selected_uploads:
        return {"error": "Please select at least one platform Excel file."}

    try:
        frames = {key: pd.DataFrame() for key in PLATFORM_UPLOADS}
        uploaded_platforms = []

        for key, upload in selected_uploads.items():
            filename = upload.filename or ""
            if not filename.lower().endswith((".xlsx", ".xlsm", ".csv")):
                return {
                    "error": (
                        f"{PLATFORM_UPLOADS[key]['label']}: unsupported file type. "
                        "Please upload an .xlsx, .xlsm, or .csv file."
                    )
                }

            contents = await upload.read()
            if not contents:
                return {"error": f"{PLATFORM_UPLOADS[key]['label']}: the selected file is empty."}
            if len(contents) > 50 * 1024 * 1024:
                return {"error": f"{PLATFORM_UPLOADS[key]['label']}: the file exceeds the 50 MB limit."}

            try:
                frames[key] = _read_platform_file(contents, filename, PLATFORM_UPLOADS[key]["sheet"])
            except Exception as exc:
                return {"error": f"{PLATFORM_UPLOADS[key]['label']}: could not read the uploaded file ({exc})."}

            uploaded_platforms.append(PLATFORM_UPLOADS[key]["label"])

        records = process_data(
            frames["fb"],
            frames["ig"],
            frames["yt"],
            frames["tt"],
            frames["li"],
            ig_story=frames["ig_story"],
        )
        if not records:
            return {"error": "No valid content records were found in the uploaded files."}

        synced = 0
        for rec in records:
            date_val = None
            if rec.get('date'):
                try:
                    date_val = pd.to_datetime(rec['date']).to_pydatetime()
                except:
                    date_val = None

            values = {
                "id":              str(rec['id']),
                "platform":        rec.get('platform', ''),
                "format":          rec.get('format', ''),
                "collab":          rec.get('collab', ''),
                "date":            date_val,
                "title":           rec.get('title', ''),
                "link":            rec.get('link', ''),
                "reach":           float(rec.get('reach') or 0),
                "views":           float(rec.get('views') or 0),
                "engagement":      float(rec.get('engagement') or 0),
                "likes":           float(rec.get('likes') or 0),
                "comments":        float(rec.get('comments') or 0),
                "shares":          float(rec.get('shares') or 0),
                "favorites":       float(rec.get('favorites') or 0),
                "reposts":         float(rec.get('reposts') or 0),
                "impressions":     float(rec.get('impressions') or 0),
                "watch_time_hours": float(rec.get('watch_time_hours') or 0),
                "engagement_rate": float(rec.get('engagement_rate') or 0),
                "is_organic":      bool(rec.get('is_organic', True)),
            }

            # Native PostgreSQL UPSERT — works with connection poolers, never throws duplicate errors
            stmt = pg_insert(Post).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={k: v for k, v in values.items() if k != "id"}
            )
            db.execute(stmt)
            synced += 1

        db.commit()
        return {
            "message": f"Upload complete! {synced} content records synced to the database.",
            "synced": synced,
            "platforms": uploaded_platforms,
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Upload failed: {str(e)}"}


# ── Posts CRUD endpoints ───────────────────────────────────────────────────────
@app.get("/api/posts")
def get_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    platform: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    query = db.query(Post)
    if platform:
        query = query.filter(Post.platform == platform)
    if search:
        query = query.filter(Post.title.ilike(f"%{search}%"))
    if start_date:
        query = query.filter(Post.date >= pd.to_datetime(start_date))
    if end_date:
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1, seconds=-1)
        query = query.filter(Post.date <= end_dt)
    total = query.count()
    date_sort = Post.date.asc().nullslast() if sort_order == "asc" else Post.date.desc().nullslast()
    posts = query.order_by(date_sort, Post.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total, "page": page, "limit": limit,
        "pages": math.ceil(total / limit),
        "posts": [
            {
                "id": p.id, "platform": p.platform, "format": p.format,
                "collab": getattr(p, 'collab', '') or '',
                "date": p.date.isoformat() if p.date else None,
                "title": p.title, "link": p.link,
                "reach": p.reach, "views": p.views, "engagement": p.engagement,
                "likes": p.likes, "comments": p.comments, "shares": p.shares,
                "favorites": p.favorites, "reposts": p.reposts,
                "engagement_rate": effective_engagement_rate(
                    p.platform, p.format, p.engagement, p.reach, p.views, p.engagement_rate
                ),
                "is_organic": p.is_organic,
            }
            for p in posts
        ]
    }


class PostUpdate(BaseModel):
    platform: Optional[str] = None
    format: Optional[str] = None
    collab: Optional[str] = None
    date: Optional[str] = None
    title: Optional[str] = None
    link: Optional[str] = None
    reach: Optional[float] = None
    views: Optional[float] = None
    engagement: Optional[float] = None
    likes: Optional[float] = None
    comments: Optional[float] = None
    shares: Optional[float] = None
    favorites: Optional[float] = None
    reposts: Optional[float] = None
    engagement_rate: Optional[float] = None
    is_organic: Optional[bool] = None

@app.patch("/api/posts/{post_id}")
def update_post(post_id: str, body: PostUpdate, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    data = body.dict(exclude_unset=True)
    if 'date' in data and data['date']:
        try:
            data['date'] = pd.to_datetime(data['date']).to_pydatetime()
        except:
            del data['date']
    for key, val in data.items():
        setattr(post, key, val)
    er_inputs = {'platform', 'format', 'engagement', 'reach', 'views'}
    if er_inputs.intersection(data) and 'engagement_rate' not in data:
        post.engagement_rate = effective_engagement_rate(
            post.platform, post.format, post.engagement, post.reach, post.views, post.engagement_rate
        )
    db.commit()
    return {
        "message": "Post updated successfully",
        "engagement_rate": effective_engagement_rate(
            post.platform, post.format, post.engagement, post.reach, post.views, post.engagement_rate
        ),
    }


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


class NewPost(BaseModel):
    platform: str = "Facebook"
    format: str = "Video"
    collab: str = ""
    date: Optional[str] = None
    title: str = ""
    link: str = ""
    reach: float = 0
    views: float = 0
    engagement: float = 0
    likes: float = 0
    comments: float = 0
    shares: float = 0
    favorites: float = 0
    reposts: float = 0
    engagement_rate: float = 0
    is_organic: bool = True

@app.post("/api/posts")
def create_post(body: NewPost, db: Session = Depends(get_db)):
    import uuid
    date_val = None
    if body.date:
        try:
            date_val = pd.to_datetime(body.date).to_pydatetime()
        except:
            date_val = None
    engagement_rate = effective_engagement_rate(
        body.platform, body.format, body.engagement, body.reach, body.views, body.engagement_rate
    )
    post = Post(
        id=str(uuid.uuid4()),
        platform=body.platform, format=body.format, collab=body.collab, date=date_val,
        title=body.title, link=body.link, reach=body.reach, views=body.views,
        engagement=body.engagement, likes=body.likes, comments=body.comments,
        shares=body.shares, favorites=body.favorites, reposts=body.reposts,
        engagement_rate=engagement_rate, is_organic=body.is_organic,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"message": "Post created", "id": post.id}


# ── AI Reports cache endpoints ─────────────────────────────────────────────────
@app.get("/api/ai-reports")
def get_ai_report(
    report_type: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(AiReport).filter(AiReport.report_type == report_type)
    if start_date:
        query = query.filter(AiReport.start_date == start_date)
    if end_date:
        query = query.filter(AiReport.end_date == end_date)
    report = query.order_by(AiReport.created_at.desc()).first()
    if not report:
        return {"found": False}
    return {"found": True, "content": json.loads(report.content), "created_at": report.created_at.isoformat()}


@app.post("/api/ai-reports")
def save_ai_report(
    report_type: str,
    content: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    report = AiReport(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        content=json.dumps(content)
    )
    db.add(report)
    db.commit()
    return {"message": "Report saved"}


@app.get("/api/dashboard-summary")
def get_dashboard_summary(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    df = get_filtered_data(start_date, end_date)

    total_reach = df['reach'].sum()
    total_engagement = df['engagement'].sum()
    er_denominator = df['reach'].copy()
    fb_ig_without_reach = df['platform'].isin(['Facebook', 'Instagram']) & (df['reach'] <= 0)
    er_denominator.loc[fb_ig_without_reach] = df.loc[fb_ig_without_reach, 'views']
    total_er_denominator = er_denominator.sum()
    avg_engagement_rate = (total_engagement / total_er_denominator * 100) if total_er_denominator > 0 else 0
    
    platform_group = df.groupby('platform').agg({'engagement': 'sum'}).reset_index()
    top_platform = platform_group.sort_values(by='engagement', ascending=False).iloc[0]['platform'] if not platform_group.empty else "N/A"
    
    return {
        "kpis": {
            "total_reach": float(total_reach),
            "total_engagement": float(total_engagement),
            "avg_engagement_rate": float(avg_engagement_rate),
            "top_platform": str(top_platform)
        }
    }

@app.get("/api/platform-stats")
def get_platform_stats(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    df = get_filtered_data(start_date, end_date)
    
    stats = {}
    for platform in ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']:
        pdf = df[df['platform'] == platform]
        if pdf.empty:
            stats[platform] = None
            continue
        
        posts_count = len(pdf)
        avg_reach = float(pdf['reach'].mean()) if posts_count > 0 else 0
        avg_er = float(pdf['engagement_rate'].mean()) if posts_count > 0 else 0
            
        stats[platform] = {
            "posts_count": posts_count,
            "avg_reach": avg_reach,
            "avg_engagement_rate": avg_er
        }
        
    return stats

@app.get("/api/organic-content")
def get_organic_content(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    df = get_filtered_data(start_date, end_date)
    
    def clean_records(df_subset):
        res = []
        for r in df_subset.to_dict(orient='records'):
            clean_r = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k,v in r.items()}
            if pd.notnull(clean_r['date']):
                clean_r['date'] = str(clean_r['date'])
            res.append(clean_r)
        return res

    result = {}
    for platform in ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']:
        org = df[(df['platform'] == platform) & (df['is_organic'] == True)]
        
        if org.empty:
            result[platform] = {"top": [], "bottom": []}
            continue
            
        org = org.sort_values(by='engagement', ascending=False)
        
        top5 = clean_records(org.head(5))
        bottom5 = clean_records(org.tail(5))
        
        result[platform] = {
            "top": top5,
            "bottom": bottom5
        }
    
    return result


@app.get("/api/engagement-summary")
def get_engagement_summary(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    df = get_filtered_data(start_date, end_date)

    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']
    platform_data = []
    overall_total = 0
    overall_posts = 0

    for platform in platforms:
        pdf = df[df['platform'] == platform]
        if pdf.empty:
            continue
        total_eng = float(pdf['engagement'].sum())
        posts = len(pdf)
        avg_eng = total_eng / posts if posts > 0 else 0
        overall_total += total_eng
        overall_posts += posts
        platform_data.append({
            "platform": platform,
            "total_engagement": total_eng,
            "posts_count": posts,
            "avg_engagement_per_post": avg_eng,
        })

    return {
        "platforms": platform_data,
        "overall": {
            "total_engagement": overall_total,
            "posts_count": overall_posts,
            "avg_engagement_per_post": overall_total / overall_posts if overall_posts > 0 else 0,
        }
    }

# ---------------------------------------------------------------------------
# Content-type classification
# ---------------------------------------------------------------------------
# Ordered priority list: first matching rule wins.
CONTENT_TYPE_RULES = [
    ("Raya / Festive",         ["raya", "hari raya", "aidilfitri", "aidiladha", "ramadan", "festive", "cny", "chinese new year", "deepavali", "diwali", "christmas", "new year", "merdeka", "hari kebangsaan"]),
    ("Creator Collaboration",  ["collab", "collaboration", "creator", "influencer", "x ", "feat.", "featuring", "bersama", "ft."]),
    ("Security / Fraud Alert", ["scam", "fraud", "phishing", "jangan mudah", "protect", "security", "selamat", "secure", "alert", "penipuan", "beware", "warning"]),
    # NOTE: "App Features" removed — "app" keyword was too broad and was misclassifying unrelated posts.
    # App Tutorial kept with tighter keywords that imply instructional content.
    ("App Tutorial",           ["tutorial", "how to", "how-to", "cara ", "step by step", "panduan", "guide", "langkah", "learn how"]),
    ("Financial Literacy",     ["financial literacy", "kewangan", "money tip", "tip kewangan", "budgeting", "bajet", "savings", "simpanan", "investment", "pelaburan", "financial planning", "wealth", "unit trust", "amanah saham", "finance tip", "financial tip", "did you know", "tahukah anda"]),
    ("Product Promotion",      ["promo", "promotion", "offer", "deal", "discount", "cashback", "reward", "kredit", "credit card", "kad kredit", "loan", "pinjaman", "mortgage", "home loan", "personal loan", "rate", "kadar", "apply now", "daftar sekarang", "special rate"]),
    ("Market Outlook",         ["market outlook", "economy", "economic", "gdp", "inflation", "interest rate", "bnm", "bank negara", "quarter", "q1", "q2", "q3", "q4", "forecast", "ringgit", "bursa", "klse"]),
    ("Awards / Recognition",   ["award", "recognition", "winner", "excellence", "best bank", "achievement", "accolade", "rated", "ranking", "ranked"]),
    ("Announcements",          ["announcement", "announce", "introducing", "new launch", "launching", "press release", "media release"]),
    ("Brand / CSR",            ["csr", "community", "sustainability", "environment", "charity", "donation", "green", "social responsibility", "gotong royong", "kesukarelawan", "volunteer", "wakaf", "zakat", "sedekah"]),
    ("ASEAN Culture",          ["asean", "malaysia", "malaysian", "budaya", "heritage", "tradition", "warisan", "kebudayaan", "local culture"]),
    ("Event Recap",            ["event", "recap", "highlight", "ceremony", "launch event", "conference", "summit", "forum", "seminar", "webinar", "workshop"]),
    ("Interactive",            ["quiz", "poll", "challenge", "contest", "giveaway", "win ", "tag a friend", "share your", "comment below", "tell us", "vote"]),
    ("Talent / Career",        ["career", "hiring", "job", "talent", "employee", "kerjaya", "team member", "join us", "we are hiring", "internship"]),
    ("SME / Business Banking", ["sme", "business", "entrepreneur", "enterprise", "corporate", "trade finance", "usahawan", "perniagaan", "b2b"]),
    ("Campaign Video",         ["campaign", "video campaign", "tv ad", "advertisement", "ad "]),
]
FALLBACK_TYPE = "General / Other"


def classify_content_type(title: str) -> str:
    """Return the first matching content-type label for a post title."""
    if not title or title.strip().lower() in ("", "nan", "none"):
        return FALLBACK_TYPE
    text = title.lower()
    for label, keywords in CONTENT_TYPE_RULES:
        if any(kw in text for kw in keywords):
            return label
    return FALLBACK_TYPE


@app.get("/api/content-types")
def get_content_types(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    """Return content-type breakdown (post counts) per platform + overall."""
    df = get_filtered_data(start_date, end_date)

    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']
    result = {}
    overall_counts: dict[str, int] = {}

    for platform in platforms:
        pdf = df[df['platform'] == platform]
        if pdf.empty:
            result[platform] = []
            continue

        counts: dict[str, int] = {}
        for title in pdf['title'].fillna(''):
            ct = classify_content_type(str(title))
            counts[ct] = counts.get(ct, 0) + 1

        # Sort by count desc
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        result[platform] = [{"type": t, "count": c} for t, c in sorted_counts]

        for t, c in counts.items():
            overall_counts[t] = overall_counts.get(t, 0) + c

    result["Overall"] = [
        {"type": t, "count": c}
        for t, c in sorted(overall_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    return result


@app.get("/api/all-content")
def get_all_content(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    df = get_filtered_data(start_date, end_date)

    def clean_records(df_subset):
        res = []
        for r in df_subset.to_dict(orient='records'):
            clean_r = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k,v in r.items()}
            if pd.notnull(clean_r['date']):
                clean_r['date'] = str(clean_r['date'])
            res.append(clean_r)
        return res

    result = {}
    for platform in ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']:
        org = df[(df['platform'] == platform) & (df['is_organic'] == True)]
        if org.empty:
            result[platform] = []
            continue
        org = org.sort_values(by='engagement', ascending=False)
        result[platform] = clean_records(org)

    return result


@app.get("/api/format-performance")
def get_format_performance(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    df = get_filtered_data(start_date, end_date)
    
    platforms = ['Facebook', 'Instagram', 'LinkedIn', 'TikTok', 'YouTube']
    result = []
    
    grand_posts = 0
    grand_reach = 0
    grand_eng = 0
    grand_er_sum = 0
    
    for platform in platforms:
        pdf = df[(df['platform'] == platform) & (df['is_organic'] == True)]
        if pdf.empty:
            continue
            
        platform_posts = 0
        platform_reach = 0
        platform_eng = 0
        platform_er_sum = 0
        
        formats = pdf['format'].unique()
        for fmt in sorted(formats):
            fdf = pdf[pdf['format'] == fmt]
            content_count = len(fdf)
            if content_count == 0: continue
            reach_sum = fdf['reach'].sum()
            eng_sum = fdf['engagement'].sum()
            er_mean = fdf['engagement_rate'].mean()
            
            platform_posts += content_count
            platform_reach += reach_sum
            platform_eng += eng_sum
            platform_er_sum += er_mean * content_count
            
            result.append({
                "platform": platform,
                "format": fmt,
                "is_total": False,
                "posts": content_count,
                "avg_reach": reach_sum / content_count,
                "avg_engagement": eng_sum / content_count,
                "avg_er": er_mean
            })
            
        if platform_posts > 0:
            result.append({
                "platform": platform,
                "format": f"{platform} Total",
                "is_total": True,
                "posts": platform_posts,
                "avg_reach": platform_reach / platform_posts,
                "avg_engagement": platform_eng / platform_posts,
                "avg_er": platform_er_sum / platform_posts
            })
            
            grand_posts += platform_posts
            grand_reach += platform_reach
            grand_eng += platform_eng
            grand_er_sum += platform_er_sum
            
    if grand_posts > 0:
        result.append({
            "platform": "Grand Total",
            "format": "",
            "is_total": True,
            "is_grand_total": True,
            "posts": grand_posts,
            "avg_reach": grand_reach / grand_posts,
            "avg_engagement": grand_eng / grand_posts,
            "avg_er": grand_er_sum / grand_posts
        })
        
    return result


ALL_CONTENT_EXPORT_COLUMNS = [
    'Date(Publish)', 'Platform', 'Format', 'Pillar', 'Organic/Paid',
    'Collab', 'Title', 'Caption', 'Reach', 'Views', 'Interaction',
    'ER%', 'Likes', 'Comments', 'Shares', 'Saves', 'Reposts', 'URL', 'Year Month'
]


def build_all_contents_export(df: pd.DataFrame) -> pd.DataFrame:
    """Convert database content records to the established All Contents layout."""
    rows = []
    for row in df.sort_values('date', ascending=True).to_dict(orient='records'):
        dt = pd.to_datetime(row.get('date'), errors='coerce')
        if pd.isna(dt):
            continue

        platform = str(row.get('platform') or '')
        rows.append({
            'Date(Publish)': dt.date(),
            'Platform': platform,
            'Format': str(row.get('format') or ''),
            'Pillar': '',
            'Organic/Paid': 'Organic' if row.get('is_organic') is not False else 'Paid',
            'Collab': str(row.get('collab') or ''),
            'Title': '',
            'Caption': str(row.get('title') or ''),
            'Reach': float(row.get('reach') or 0),
            'Views': float(row.get('views') or 0),
            'Interaction': float(row.get('engagement') or 0),
            'ER%': round(float(row.get('engagement_rate') or 0), 2),
            'Likes': float(row.get('likes') or 0),
            'Comments': float(row.get('comments') or 0),
            'Shares': '' if platform == 'LinkedIn' else float(row.get('shares') or 0),
            'Saves': float(row.get('favorites') or 0) if platform in ('Instagram', 'TikTok') else '',
            'Reposts': float(row.get('reposts') or 0) if platform == 'LinkedIn' else '',
            'URL': str(row.get('link') or ''),
            'Year Month': dt.strftime('%Y %B'),
        })

    return pd.DataFrame(rows, columns=ALL_CONTENT_EXPORT_COLUMNS)


@app.get("/api/export-all-contents")
def export_all_contents(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Export all database contents (organic + paid) for the selected date range."""
    df_export = build_all_contents_export(get_filtered_data(start_date, end_date))

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='All Contents')
        ws = writer.sheets['All Contents']
        for col in ws.columns:
            max_len = max((len(str(cell.value)) if cell.value else 0) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    output.seek(0)

    period = f"{start_date or 'all'}_{end_date or 'present'}"
    filename = f"CIMB_All_Contents_{period}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


def export_all_contents_from_sheet_legacy(
    sheet_url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Legacy Google Sheet exporter retained for reference; it is no longer routed."""
    import re
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_url)
    if not match:
        return {"error": "Invalid Google Sheet URL. Could not extract spreadsheet ID."}
    sheet_id = match.group(1)
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

    try:
        xl = pd.ExcelFile(export_url)
    except Exception as e:
        return {"error": f"Failed to download Google Sheet: {str(e)}"}

    def _get(row, *keys, default=''):
        for k in keys:
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                return v
        return default

    def _num(row, *keys):
        for k in keys:
            v = row.get(k)
            try:
                f = float(v)
                if not math.isnan(f): return f
            except: pass
        return 0.0

    def _in_range(dt):
        if pd.isna(dt): return False
        if start_date and dt < pd.to_datetime(start_date): return False
        if end_date:
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1, seconds=-1)
            if dt > end_dt: return False
        return True

    rows = []

    # ── Facebook ────────────────────────────────────────────────────────────────
    if 'Raw_FB' in xl.sheet_names:
        fb = xl.parse('Raw_FB')
        for _, row in fb.iterrows():
            dt = pd.to_datetime(row.get('Publish time'), errors='coerce')
            if not _in_range(dt): continue
            views = _num(row, 'Views')
            reach = _num(row, 'Reach', 'Lifetime Post Total Reach')
            reactions = _num(row, 'Reactions, comments and shares')
            comments = _num(row, 'Comments')
            shares = _num(row, 'Shares')
            likes = max(0, reactions - comments - shares)
            total_eng = reactions
            er = round(total_eng / reach * 100, 2) if reach > 0 else 0
            rows.append({
                'Date(Publish)': dt.date(),
                'Platform': 'Facebook',
                'Format': str(_get(row, 'Post type')),
                'Pillar': '',
                'Organic/Paid': str(_get(row, 'Organic/Paid')),
                'Collab': str(_get(row, 'Collab')),
                'Title': '',
                'Caption': str(_get(row, 'Description', 'Post message', 'Title')),
                'Reach': reach,
                'Views': views,
                'Interaction': total_eng,
                'ER%': er,
                'Likes': likes,
                'Comments': comments,
                'Shares': shares,
                'Saves': '',
                'Reposts': '',
                'URL': str(_get(row, 'Permalink', 'Link')),
                'Year Month': dt.strftime('%Y %B'),
            })

    # ── Instagram ───────────────────────────────────────────────────────────────
    if 'Raw_IG' in xl.sheet_names:
        ig = xl.parse('Raw_IG')
        for _, row in ig.iterrows():
            dt = pd.to_datetime(row.get('Publish time'), errors='coerce')
            if not _in_range(dt): continue
            views = _num(row, 'Views')
            reach = _num(row, 'Reach')
            likes = _num(row, 'Likes')
            comments = _num(row, 'Comments')
            shares = _num(row, 'Shares')
            saves = _num(row, 'Saves')
            total_eng = likes + comments + shares + saves
            er = round(total_eng / reach * 100, 2) if reach > 0 else 0
            rows.append({
                'Date(Publish)': dt.date(),
                'Platform': 'Instagram',
                'Format': str(_get(row, 'Post type')),
                'Pillar': '',
                'Organic/Paid': str(_get(row, 'Organic/Paid')),
                'Collab': str(_get(row, 'Collab')),
                'Title': '',
                'Caption': str(_get(row, 'Description')),
                'Reach': reach,
                'Views': views,
                'Interaction': total_eng,
                'ER%': er,
                'Likes': likes,
                'Comments': comments,
                'Shares': shares,
                'Saves': saves,
                'Reposts': '',
                'URL': str(_get(row, 'Permalink')),
                'Year Month': dt.strftime('%Y %B'),
            })

    # ── YouTube ─────────────────────────────────────────────────────────────────
    if 'Raw_Youtube' in xl.sheet_names:
        yt = xl.parse('Raw_Youtube')
        for _, row in yt.iterrows():
            dt = pd.to_datetime(row.get('Video publish time'), errors='coerce')
            if not _in_range(dt): continue
            views = _num(row, 'Views')
            likes = _num(row, 'Likes')
            comments = _num(row, 'Comments added')
            shares = _num(row, 'Shares')
            total_eng = likes + comments + shares
            er = round(total_eng / views * 100, 2) if views > 0 else 0
            rows.append({
                'Date(Publish)': dt.date(),
                'Platform': 'YouTube',
                'Format': 'Video',
                'Pillar': '',
                'Organic/Paid': str(_get(row, 'Organic/ Paid', 'Organic/Paid')),
                'Collab': str(_get(row, 'Collab')),
                'Title': '',
                'Caption': str(_get(row, 'Video title')),
                'Reach': views,
                'Views': views,
                'Interaction': total_eng,
                'ER%': er,
                'Likes': likes,
                'Comments': comments,
                'Shares': shares,
                'Saves': '',
                'Reposts': '',
                'URL': f"https://youtube.com/watch?v={_get(row, 'Content')}",
                'Year Month': dt.strftime('%Y %B'),
            })

    # ── TikTok ──────────────────────────────────────────────────────────────────
    if 'Raw_Tiktok' in xl.sheet_names:
        tt = xl.parse('Raw_Tiktok')
        for _, row in tt.iterrows():
            dt = pd.to_datetime(row.get('Post time'), errors='coerce')
            if not _in_range(dt): continue
            views = _num(row, 'Video views')
            if views < 10: continue   # keep same filter as main pipeline
            likes = _num(row, 'Likes')
            comments = _num(row, 'Comments')
            shares = _num(row, 'Shares')
            favorites = _num(row, 'Add to Favorites')
            total_eng = likes + comments + shares + favorites
            er = round(total_eng / views * 100, 2) if views > 0 else 0
            rows.append({
                'Date(Publish)': dt.date(),
                'Platform': 'TikTok',
                'Format': 'Video',
                'Pillar': '',
                'Organic/Paid': str(_get(row, 'Organic/Paid')),
                'Collab': str(_get(row, 'Collab')),
                'Title': '',
                'Caption': str(_get(row, 'Video description', 'Video title')),
                'Reach': views,
                'Views': views,
                'Interaction': total_eng,
                'ER%': er,
                'Likes': likes,
                'Comments': comments,
                'Shares': shares,
                'Saves': favorites,
                'Reposts': '',
                'URL': str(_get(row, 'Video link')),
                'Year Month': dt.strftime('%Y %B'),
            })

    # ── LinkedIn ────────────────────────────────────────────────────────────────
    if 'Raw_LI' in xl.sheet_names:
        li = xl.parse('Raw_LI')
        for _, row in li.iterrows():
            dt = pd.to_datetime(row.get('Created date'), errors='coerce')
            if not _in_range(dt): continue
            impressions = _num(row, 'Impressions')
            views = _num(row, 'Views')
            likes = _num(row, 'Likes')
            comments = _num(row, 'Comments')
            reposts = _num(row, 'Reposts')
            total_eng = likes + comments + reposts
            er = round(total_eng / impressions * 100, 2) if impressions > 0 else 0
            rows.append({
                'Date(Publish)': dt.date(),
                'Platform': 'LinkedIn',
                'Format': str(_get(row, 'Content Type')),
                'Pillar': '',
                'Organic/Paid': str(_get(row, 'Organic/Paid')),
                'Collab': str(_get(row, 'Collab')),
                'Title': '',
                'Caption': str(_get(row, 'Post content', 'Update title', 'Post title')),
                'Reach': impressions,
                'Views': views,
                'Interaction': total_eng,
                'ER%': er,
                'Likes': likes,
                'Comments': comments,
                'Shares': '',
                'Saves': '',
                'Reposts': reposts,
                'URL': str(_get(row, 'Post link')),
                'Year Month': dt.strftime('%Y %B'),
            })

    # ── Build DataFrame & sort by date ──────────────────────────────────────────
    df_export = pd.DataFrame(rows, columns=[
        'Date(Publish)', 'Platform', 'Format', 'Pillar', 'Organic/Paid',
        'Collab', 'Title', 'Caption', 'Reach', 'Views', 'Interaction',
        'ER%', 'Likes', 'Comments', 'Shares', 'Saves', 'Reposts', 'URL', 'Year Month'
    ])
    df_export = df_export.sort_values('Date(Publish)', ascending=True).reset_index(drop=True)

    # ── Write to Excel in memory ─────────────────────────────────────────────────
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='All Contents')
        ws = writer.sheets['All Contents']
        # Auto-fit column widths
        for col in ws.columns:
            max_len = max((len(str(cell.value)) if cell.value else 0) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    output.seek(0)

    period = f"{start_date or 'all'}_{end_date or 'present'}"
    filename = f"CIMB_All_Contents_{period}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.get("/api/pillar-er")
def get_pillar_er(
    sheet_url: str = Query(..., description="Public Google Sheet URL"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Read the 'All Contents' sheet from the user-supplied Google Sheet URL,
    filter to Organic rows only, and return avg ER% pivot: Pillar × Platform.
    """
    # Convert any edit/view URL to an xlsx export URL
    import re
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_url)
    if not match:
        return {"error": "Invalid Google Sheet URL. Could not extract spreadsheet ID."}
    sheet_id = match.group(1)
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

    try:
        xl = pd.ExcelFile(export_url)
    except Exception as e:
        return {"error": f"Could not read the Google Sheet. Make sure it is publicly shared. ({e})"}

    # Find the correct sheet — try common names
    target_sheet = None
    for candidate in ["All Contents", "All Content", "All contents", "all contents"]:
        if candidate in xl.sheet_names:
            target_sheet = candidate
            break
    if target_sheet is None:
        return {
            "error": f"Could not find an 'All Contents' sheet. Sheets found: {xl.sheet_names}"
        }

    df = xl.parse(target_sheet)

    # Normalise column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]
    df = exclude_instagram_stories_from_dataframe(df)

    required = {"Pillar", "Platform", "Organic/Paid", "ER%"}
    missing = required - set(df.columns)
    if missing:
        # Try alternative ER column names
        for alt in ["ER %", "Engagement Rate", "Engagement Rate %"]:
            if alt in df.columns:
                df.rename(columns={alt: "ER%"}, inplace=True)
                missing = required - set(df.columns)
                break
    if missing:
        return {"error": f"Required columns missing from sheet: {missing}. Found: {df.columns.tolist()}"}

    # Date filter
    if "Date(Publish)" in df.columns:
        df["Date(Publish)"] = pd.to_datetime(df["Date(Publish)"], errors="coerce")
        if start_date:
            df = df[df["Date(Publish)"] >= pd.to_datetime(start_date)]
        if end_date:
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1, seconds=-1)
            df = df[df["Date(Publish)"] <= end_dt]

    # Filter organic only
    organic_mask = df["Organic/Paid"].astype(str).str.strip().str.lower() == "organic"
    df = df[organic_mask].copy()

    # Clean ER% — strip % signs, coerce to float
    df["ER%"] = (
        df["ER%"].astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
    )

    # Drop rows with no Pillar, no Platform, or no ER
    df = df.dropna(subset=["Pillar", "Platform", "ER%"])
    df = df[df["Pillar"].astype(str).str.strip() != ""]

    # Build pivot: rows = Pillar, cols = Platform, values = mean ER%
    platforms = ["Facebook", "Instagram", "LinkedIn", "TikTok", "YouTube"]
    pillars = sorted(df["Pillar"].astype(str).str.strip().unique())

    pivot = []
    for pillar in pillars:
        pdata = {"pillar": pillar}
        pf = df[df["Pillar"].astype(str).str.strip() == pillar]
        for plat in platforms:
            plat_df = pf[pf["Platform"].astype(str).str.strip() == plat]
            if plat_df.empty:
                pdata[plat] = None
            else:
                pdata[plat] = round(float(plat_df["ER%"].mean()), 2)
        pivot.append(pdata)

    return {"platforms": platforms, "pivot": pivot}


@app.get("/api/export-cross-platform")
def export_cross_platform(
    sheet_url: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    import re
    from openpyxl.styles import PatternFill, Font, Alignment

    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_url)
    if not match:
        return {"error": "Invalid Google Sheet URL."}
    export_url = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=xlsx"

    try:
        xl = pd.ExcelFile(export_url)
    except Exception as e:
        return {"error": f"Could not read sheet: {e}"}

    target = next((s for s in xl.sheet_names if s.lower().startswith("all content")), None)
    if not target:
        return {"error": f"No 'All Contents' sheet found. Sheets: {xl.sheet_names}"}

    df = xl.parse(target)
    df.columns = [str(c).strip() for c in df.columns]
    df = exclude_instagram_stories_from_dataframe(df)

    # Date filter
    if "Date(Publish)" in df.columns:
        df["Date(Publish)"] = pd.to_datetime(df["Date(Publish)"], errors="coerce")
        if start_date:
            df = df[df["Date(Publish)"] >= pd.to_datetime(start_date)]
        if end_date:
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1, seconds=-1)
            df = df[df["Date(Publish)"] <= end_dt]

    # Normalise ER%
    if "ER%" in df.columns:
        df["ER%"] = pd.to_numeric(
            df["ER%"].astype(str).str.replace("%", "", regex=False).str.strip(),
            errors="coerce"
        )

    PLATFORMS = ["Facebook", "Instagram", "LinkedIn", "TikTok", "YouTube"]
    URL_COLS = {
        "Instagram": "IG URL", "TikTok": "TT URL",
        "Facebook": "FB URL", "YouTube": "YT URL", "LinkedIn": "LI URL"
    }

    # Sort by Pillar so same-pillar rows stay together
    sort_cols = ["Pillar"] + (["Date(Publish)"] if "Date(Publish)" in df.columns else [])
    df = df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    # Build one output row per unique normalized Caption
    seen = {}          # norm_cap -> first-seen order index
    groups = {}        # norm_cap -> {original_caption, pillar, title, plat_er, plat_url}

    for _, row in df.iterrows():
        caption = str(row.get("Caption", "")).strip()
        if not caption or caption == "nan":
            continue
            
        # Normalize the caption: ignore newlines, punctuation, whitespace
        norm_cap = re.sub(r'[\W_]+', '', caption).lower()
        if not norm_cap:
            norm_cap = caption.strip().lower()
            
        if norm_cap not in groups:
            seen[norm_cap] = len(seen)
            groups[norm_cap] = {
                "original_caption": caption,
                "pillar": str(row.get("Pillar", "") or "").strip(),
                "title":  str(row.get("Title", "")  or "").strip(),
                "er":  {},
                "url": {}
            }
        g = groups[norm_cap]
        plat = str(row.get("Platform", "")).strip()
        if plat in PLATFORMS and plat not in g["er"]:
            er_val = row.get("ER%")
            if er_val is not None and not (isinstance(er_val, float) and math.isnan(er_val)):
                g["er"][plat] = float(er_val)
            url_val = row.get("URL", row.get("URL.1", ""))
            g["url"][plat] = str(url_val) if url_val and str(url_val) != "nan" else ""

    # Build ordered output (sorted by pillar then first-seen)
    ordered = sorted(groups.keys(), key=lambda c: (groups[c]["pillar"], seen[c]))

    output_rows = []
    i = 0
    while i < len(ordered):
        pillar = groups[ordered[i]]["pillar"]
        # Collect all normalized captions for this pillar
        pillar_captions = []
        while i < len(ordered) and groups[ordered[i]]["pillar"] == pillar:
            pillar_captions.append(ordered[i])
            i += 1

        first_in_pillar = True
        # Accumulate platform ER values across this pillar for totals
        pillar_plat_ers = {p: [] for p in PLATFORMS}

        for norm_cap in pillar_captions:
            g = groups[norm_cap]
            valid_ers = [v for v in g["er"].values() if v is not None]
            grand_total = round(sum(valid_ers) / len(valid_ers), 2) if valid_ers else None

            output_rows.append({
                "Pillar":      pillar if first_in_pillar else "",
                "New Title":   g["title"] if g["title"] not in ("", "nan") else "",
                "Caption":     g["original_caption"],
                "Facebook":    g["er"].get("Facebook"),
                "Instagram":   g["er"].get("Instagram"),
                "LinkedIn":    g["er"].get("LinkedIn"),
                "TikTok":      g["er"].get("TikTok"),
                "YouTube":     g["er"].get("YouTube"),
                "Grand Total": grand_total,
                "IG URL":      g["url"].get("Instagram", ""),
                "TT URL":      g["url"].get("TikTok", ""),
                "FB URL":      g["url"].get("Facebook", ""),
                "YT URL":      g["url"].get("YouTube", ""),
                "LI URL":      g["url"].get("LinkedIn", ""),
                "_is_total":   False,
            })
            first_in_pillar = False

            for p in PLATFORMS:
                if g["er"].get(p) is not None:
                    pillar_plat_ers[p].append(g["er"][p])

        # Pillar Total row — average ER% per platform (2 dp)
        total_er = {
            p: round(sum(vals) / len(vals), 2) if vals else None
            for p, vals in pillar_plat_ers.items()
        }
        all_valid = [v for v in total_er.values() if v is not None]
        total_grand = round(sum(all_valid) / len(all_valid), 2) if all_valid else None

        output_rows.append({
            "Pillar":      f"{pillar} Total",
            "New Title":   "",
            "Caption":     "",
            "Facebook":    total_er.get("Facebook"),
            "Instagram":   total_er.get("Instagram"),
            "LinkedIn":    total_er.get("LinkedIn"),
            "TikTok":      total_er.get("TikTok"),
            "YouTube":     total_er.get("YouTube"),
            "Grand Total": total_grand,
            "IG URL":      "",
            "TT URL":      "",
            "FB URL":      "",
            "YT URL":      "",
            "LI URL":      "",
            "_is_total":   True,
        })

    COLS = ["Pillar","New Title","Caption","Facebook","Instagram","LinkedIn",
            "TikTok","YouTube","Grand Total","IG URL","TT URL","FB URL","YT URL","LI URL"]

    is_total_flags = [r.pop("_is_total") for r in output_rows]
    df_out = pd.DataFrame(output_rows, columns=COLS)

    # URL column indices (0-based in df = 1-based + 1 header in ws)
    URL_COL_NAMES = ["IG URL","TT URL","FB URL","YT URL","LI URL"]
    url_col_letters = {
        name: chr(ord('A') + COLS.index(name))
        for name in URL_COL_NAMES
    }

    # Write Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Cross Platform Contents Perform")
        ws = writer.sheets["Cross Platform Contents Perform"]

        from openpyxl.styles import Border, Side
        grey_fill  = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        total_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        header_font = Font(bold=True, color="000000")
        total_font  = Font(bold=True, color="000000")
        link_font   = Font(color="0563C1", underline="single")

        # Header row — light grey, bold
        for cell in ws[1]:
            cell.fill = grey_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        # Data rows
        for row_idx, is_total in enumerate(is_total_flags, start=2):
            if is_total:
                for cell in ws[row_idx]:
                    cell.fill = total_fill
                    cell.font = total_font

        # Make URL cells clickable hyperlinks
        for col_name, col_letter in url_col_letters.items():
            col_idx = COLS.index(col_name) + 1  # openpyxl is 1-based
            for row_idx in range(2, ws.max_row + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                url_val = str(cell.value or "").strip()
                if url_val and url_val.startswith("http"):
                    cell.hyperlink = url_val
                    cell.value = url_val
                    cell.font = link_font

        # Auto-width
        for col in ws.columns:
            width = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(width + 4, 80)

    buf.seek(0)
    period = f"{start_date or 'all'}_{end_date or 'present'}"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Cross_Platform_Contents_Performance_{period}.xlsx"'}
    )


@app.get("/api/follower-growth")
def get_follower_growth(
    sheet_url: str = Query(..., description="Public Google Sheet URL"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    Read follower count tabs from the Google Sheet and return month-by-month
    follower data per platform, filtered to the requested date range.

    Expected sheet tabs: [FB] Followers, [IG] Followers, [TT] Followers,
                         [YT] Followers, [LI] Followers
    Expected columns:    Month (date-like) + Followers (numeric)
    """
    import re as _re
    match = _re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_url)
    if not match:
        return {"error": "Invalid Google Sheet URL."}
    export_url = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=xlsx"

    try:
        xl = pd.ExcelFile(export_url)
    except Exception as e:
        return {"error": f"Could not download sheet: {e}"}

    # Map: platform → possible sheet tab names
    PLATFORM_SHEETS = {
        "Facebook":  ["[FB] Followers", "FB Followers", "Facebook Followers"],
        "Instagram": ["[IG] Followers", "IG Followers", "Instagram Followers"],
        "TikTok":    ["[TT] Followers", "TT Followers", "TikTok Followers"],
        "YouTube":   ["[YT] Followers", "YT Followers", "YouTube Followers"],
        "LinkedIn":  ["[LI] Followers", "LI Followers", "LinkedIn Followers"],
    }

    result = {}

    # Parse date filter bounds
    start_dt = pd.to_datetime(start_date) if start_date else None
    end_dt   = pd.to_datetime(end_date)   if end_date   else None
    # Expand end to end-of-day so month comparisons work correctly
    if end_dt is not None and end_dt.time() == pd.Timestamp('00:00:00').time():
        end_dt = end_dt + pd.Timedelta(days=1, seconds=-1)

    for platform, candidates in PLATFORM_SHEETS.items():
        tab = next((c for c in candidates if c in xl.sheet_names), None)
        if tab is None:
            continue

        try:
            df_f = xl.parse(tab)
        except Exception:
            continue

        df_f.columns = [str(c).strip() for c in df_f.columns]

        # Find the month column (first column that looks date-like)
        month_col = None
        for col in df_f.columns:
            sample = df_f[col].dropna().head(5)
            try:
                pd.to_datetime(sample)
                month_col = col
                break
            except Exception:
                continue
        if month_col is None:
            # Fallback: first column
            month_col = df_f.columns[0]

        # Find the followers column (first numeric column after month)
        follower_col = None
        for col in df_f.columns:
            if col == month_col:
                continue
            if pd.to_numeric(df_f[col], errors='coerce').notna().sum() > 0:
                follower_col = col
                break
        if follower_col is None:
            continue

        df_f[month_col] = pd.to_datetime(df_f[month_col], errors='coerce')
        df_f[follower_col] = pd.to_numeric(df_f[follower_col], errors='coerce')
        df_f = df_f.dropna(subset=[month_col, follower_col])
        df_f = df_f.sort_values(month_col)

        # Apply date filter — keep rows whose month falls within the range
        if start_dt is not None:
            # Include months whose start is on or after the filter start
            df_f = df_f[df_f[month_col] >= start_dt.replace(day=1)]
        if end_dt is not None:
            df_f = df_f[df_f[month_col] <= end_dt]

        rows = []
        prev_followers = None
        for _, row in df_f.iterrows():
            month_ts = row[month_col]
            followers = int(row[follower_col])
            growth_abs  = followers - prev_followers if prev_followers is not None else None
            growth_pct  = round((growth_abs / prev_followers * 100), 2) if (prev_followers and prev_followers > 0 and growth_abs is not None) else None
            rows.append({
                "month":      month_ts.strftime("%Y-%m"),
                "month_label": month_ts.strftime("%b %Y"),
                "followers":  followers,
                "growth_abs": growth_abs,
                "growth_pct": growth_pct,
            })
            prev_followers = followers

        result[platform] = rows

    return result


@app.get("/api/executive-summary")
def get_executive_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Generate an AI executive summary for the selected date range using Groq."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"error": "GROQ_API_KEY environment variable is not set. Get a free key at https://console.groq.com"}

    df = get_filtered_data(start_date, end_date)
    if df.empty:
        return {"error": "No data available for the selected period."}

    # ── Collect per-platform analytics ─────────────────────────────────────────
    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']
    platform_data = {}

    for platform in platforms:
        pdf = df[df['platform'] == platform]
        if pdf.empty:
            continue

        posts        = len(pdf)
        total_eng    = float(pdf['engagement'].sum())
        total_reach  = float(pdf['reach'].sum())
        avg_reach    = float(pdf['reach'].mean())
        max_reach    = float(pdf['reach'].max())
        avg_er       = round(float(pdf['engagement_rate'].mean()), 2)
        max_er       = round(float(pdf['engagement_rate'].max()), 2)
        min_er       = round(float(pdf['engagement_rate'].min()), 2)

        # Format breakdown — counts and avg ER per format
        fmt_data = {}
        if 'format' in pdf.columns:
            for fmt, grp in pdf.groupby('format'):
                fmt = str(fmt).strip()
                if not fmt or fmt == 'nan':
                    continue
                fmt_data[fmt] = {
                    "posts": len(grp),
                    "avg_er": round(float(grp['engagement_rate'].mean()), 2),
                }

        # Content-type distribution — only pass if a category clearly dominates
        # (≥40% of posts), so the AI only mentions it when genuinely notable.
        ct_counts: dict = {}
        for title in pdf['title'].fillna(''):
            ct = classify_content_type(str(title))
            if ct == FALLBACK_TYPE:
                continue
            ct_counts[ct] = ct_counts.get(ct, 0) + 1
        # Only surface the top content type if it accounts for ≥40% of classified posts
        total_classified = sum(ct_counts.values())
        dominant_content_type = None
        if total_classified > 0:
            top_ct, top_ct_count = max(ct_counts.items(), key=lambda x: x[1])
            if top_ct_count / total_classified >= 0.4:
                dominant_content_type = {"type": top_ct, "share_pct": round(top_ct_count / posts * 100, 1)}

        platform_data[platform] = {
            "posts":              posts,
            "total_engagement":   int(total_eng),
            "total_reach":        int(total_reach),
            "avg_reach":          int(avg_reach),
            "peak_reach":         int(max_reach),
            "avg_er_pct":         avg_er,
            "max_er_pct":         max_er,
            "min_er_pct":         min_er,
            "format_breakdown":   fmt_data,
            "dominant_content_type": dominant_content_type,  # None if no clear majority
        }

    # Pre-rank platforms by avg ER
    er_ranking = sorted(
        [(p, d["avg_er_pct"]) for p, d in platform_data.items()],
        key=lambda x: x[1], reverse=True
    )
    rank_label = ", ".join([f"#{i+1} {p} ({er}% avg ER)" for i, (p, er) in enumerate(er_ranking)])

    period_label = f"{start_date or 'beginning'} to {end_date or 'present'}"

    # ── Build prompt ────────────────────────────────────────────────────────────
    prompt = f"""You are a senior social media strategist writing an executive summary for CIMB Bank Malaysia's management team.
Period: {period_label}
Platform ER ranking (by avg ER%): {rank_label}

Per-platform data (numbers to use — do not invent figures outside this):
{json.dumps(platform_data, indent=2)}

===========================================================================
STYLE GUIDE — read every section carefully before writing
===========================================================================

THIS IS THE TONE YOU MUST WRITE IN:
  Strategic. Human. Confident. Brief.
  Write like a sharp strategist presenting to leadership — not like a data analyst listing numbers.
  The goal is for a CMO to read one sentence and instantly know the strategic implication.

─── SECTION 1: top_platform_reason ───
  One sentence. State the platform name, its avg ER%, and one sentence about why it led.
  Do NOT list multiple formats with multiple percentages.
  Good: "[Platform] led the period with [X]% avg ER, driven by strong [Format Type] content and high audience responsiveness to [Specific content theme inferred from data]."
  Bad:  "Instagram's 4.34% average engagement rate was driven by its high engagement with IG reels, which had an average engagement rate of 4.86%, supported by the fact that IG reels accounted for 30 out of 39 posts."

─── SECTION 2: key_highlights ───
  EXACTLY 2 bullet points. Point 1 = #1 platform by ER. Point 2 = #2 platform by ER.
  FORMAT per bullet: **PlatformName** [role/position in one short phrase], [one key metric — ER% only], [optional: note on content theme if dominant_content_type is not null].
  RULES:
  - ONE number only per highlight (the avg ER%). Do not list multiple format ERs.
  - Do not say "driven by its X format which had Y% ER and Z% of posts" — too granular.
  - Think: what is the ONE strategic thing leadership needs to know about this platform?
  Good: "**[Platform A]** was the strongest all-round platform, delivering the highest content volume with above-average engagement efficiency at [X]% ER."
  Good: "**[Platform B]** remained highly efficient, recording [Y]% ER with strong reach, especially for [Theme 1] and [Theme 2] content."
  Bad:  "**TikTok**, with an average engagement rate of 1.37% and total engagement of 21250, was driven by its video format, which had an average engagement rate of 1.37%."

─── SECTION 3: audience_behaviour ───
  EXACTLY 2 bullets. These are STRATEGIC OBSERVATIONS, not data citations.
  ZERO numbers. No percentages here whatsoever.
  Write about WHAT TYPE OF CONTENT or WHAT APPROACH audiences responded to.
  Think: what creative mechanic, format style, or content theme drove responses?
  Good: "Audiences responded more strongly to [Specific engaging execution style] than [Specific underperforming execution style]."
  Good: "[Format type] remains the strongest format, especially when content uses [Specific mechanic] or [Specific delivery style]."
  Bad:  "The use of video formats drove consistent engagement across TikTok and YouTube, with average engagement rates of 1.37% and 1.1% respectively."
  BANNED in this section: any %, any number, any platform name bolded.

─── SECTION 4: recommendations ───
  One recommendation per platform. Tell the team what CONTENT to make, not what metric to hit.
  Think: what should the content team CREATE or SCALE on this platform?
  Good: "Continue as the main engagement platform. Scale [Format A], [Format B], and [Theme]-led campaigns with stronger [Mechanic] formats."
  Good: "Maintain as reach-first channel and focus on [Theme 1] and [Theme 2] content to improve engagement quality."
  Bad:  "Scale the use of IG carousels on Instagram, which had an average engagement rate of 2.89%, to further increase engagement."
  Do NOT reference specific ER percentages in recommendations. Focus on content direction.

===========================================================================
Return ONLY valid JSON (no markdown fences) in this EXACT structure:
{{
  "top_platform": "<#1 platform name>",
  "top_platform_reason": "<see style guide section 1>",
  "key_highlights": [
    "<see style guide section 2 — Point 1: #1 ER platform>",
    "<see style guide section 2 — Point 2: #2 ER platform>"
  ],
  "audience_behaviour": [
    "<see style guide section 3 — NO numbers>",
    "<see style guide section 3 — NO numbers>"
  ],
  "recommendations": {{
    "Facebook": "<content direction, not metric target>",
    "Instagram": "<content direction, not metric target>",
    "TikTok": "<content direction, not metric target>",
    "YouTube": "<content direction, not metric target>",
    "LinkedIn": "<content direction, not metric target>"
  }},
  "period": "{period_label}"
}}

Final rules:
- Only include platforms that exist in the data.
- NEVER name individual post titles.
- NEVER say "General / Other" content type.
- Bold platform names in key_highlights only: **PlatformName**."""

    # ── Call Groq ───────────────────────────────────────────────────────────────
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
        "llama3-70b-8192",
    ]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error = None
    for model_name in GROQ_MODELS:
        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2048,
            }
            resp = http_requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                    raw = raw.rsplit("```", 1)[0].strip()
                return json.loads(raw)
            elif resp.status_code in (404, 400):
                last_error = resp.text
                continue
            else:
                return {"error": f"Groq API error {resp.status_code}: {resp.text}"}
        except json.JSONDecodeError as e:
            return {"error": f"AI returned invalid JSON: {str(e)}"}
        except Exception as e:
            last_error = str(e)
            continue

    return {"error": f"No Groq model succeeded. Last error: {last_error}"}


# ── Helper: call Groq with a prompt ────────────────────────────────────────────
def _call_groq(api_key: str, prompt: str, max_tokens: int = 3000):
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
                   "llama3-70b-8192", "mixtral-8x7b-32768"]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error = None
    for model in GROQ_MODELS:
        try:
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.35, "max_tokens": max_tokens}
            resp = http_requests.post(GROQ_URL, headers=headers, json=payload, timeout=90)
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                return json.loads(raw)
            elif resp.status_code in (404, 400):
                last_error = resp.text
                continue
            else:
                return {"error": f"Groq API error {resp.status_code}: {resp.text}"}
        except json.JSONDecodeError as e:
            return {"error": f"AI returned invalid JSON: {e}"}
        except Exception as e:
            last_error = str(e)
            continue
    return {"error": f"No Groq model succeeded. Last error: {last_error}"}


@app.get("/api/strategy-insights")
def get_strategy_insights(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Generate Platform Strategy Recommendations and Key Learnings using AI."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"error": "GROQ_API_KEY not set."}

    df = get_filtered_data(start_date, end_date)
    if df.empty:
        return {"error": "No data for the selected period."}

    PLATS = ["Facebook", "Instagram", "TikTok", "YouTube", "LinkedIn"]
    period_label = f"{start_date or 'the beginning'} to {end_date or 'present'}"

    def _r(v, n=2): return round(float(v), n) if v is not None else 0

    # ── Build format-level breakdown per platform ───────────────────────────────
    plat_stats = {}
    for plat in PLATS:
        pdf = df[df["platform"] == plat]
        if pdf.empty:
            continue
        org  = pdf[pdf["is_organic"] == True]
        paid = pdf[pdf["is_organic"] == False]

        org_er  = _r(org["engagement_rate"].mean())  if not org.empty  else 0
        paid_er = _r(paid["engagement_rate"].mean()) if not paid.empty else 0
        all_er  = _r(pdf["engagement_rate"].mean())

        # Format breakdown — ALL content (organic + paid): count, avg ER, best ER, worst ER
        fmt_rows = []
        if "format" in pdf.columns:
            for fmt, grp in pdf.groupby("format"):
                fmt = str(fmt).strip()
                if not fmt or fmt == "nan" or len(grp) == 0:
                    continue
                fmt_rows.append({
                    "format": fmt,
                    "posts": len(grp),
                    "avg_er": _r(grp["engagement_rate"].mean()),
                    "best_er": _r(grp["engagement_rate"].max()),
                    "worst_er": _r(grp["engagement_rate"].min()),
                })
        fmt_rows.sort(key=lambda x: x["avg_er"], reverse=True)

        er_spread = _r(pdf["engagement_rate"].max() - pdf["engagement_rate"].min()) if not pdf.empty else 0

        # Top 5 and bottom 5 posts by ER (ALL content) — truncated title for theme inference
        title_col = "title" if "title" in pdf.columns else None
        def _title(row):
            t = str(row.get(title_col, "") or "").strip() if title_col else ""
            return t[:80] if t and t != "nan" else "(no title)"

        top5 = pdf.sort_values("engagement_rate", ascending=False).head(5)
        bot5 = pdf[pdf["engagement_rate"] > 0].sort_values("engagement_rate").head(5)
        top5_posts = [{"er": _r(r["engagement_rate"]), "title": _title(r)} for _, r in top5.iterrows()]
        bot5_posts = [{"er": _r(r["engagement_rate"]), "title": _title(r)} for _, r in bot5.iterrows()]

        plat_stats[plat] = {
            "total_posts":        len(pdf),
            "organic_posts":      len(org),
            "paid_posts":         len(paid),
            "avg_er_all":         all_er,
            "avg_er_organic":     org_er,
            "avg_er_paid":        paid_er,
            "avg_reach":          int(pdf["reach"].mean()) if not pdf.empty else 0,
            "er_spread":          er_spread,
            "format_performance": fmt_rows,
            "top5_posts":         top5_posts,
            "bot5_posts":         bot5_posts,
        }

    er_rank = sorted(plat_stats.items(), key=lambda x: x[1]["avg_er_all"], reverse=True)
    er_rank_str = ", ".join([f"{p} ({d['avg_er_all']}% avg ER, {d['total_posts']} total posts, {d['organic_posts']} organic)" for p, d in er_rank])

    data_str = json.dumps(plat_stats, indent=2)


    # ── Prompt 1: Platform Strategy ─────────────────────────────────────────────
    prompt1 = f"""You are a senior social media strategist producing a board-level report for CIMB Bank Malaysia.
Period: {period_label}
Platform organic ER ranking: {er_rank_str}

Per-platform analytics (format breakdown + top/bottom post titles for theme context):
{data_str}

TASK: Write a STOP / PAUSE / CONTINUE / ENHANCE strategy for each platform.

WRITING DOCTRINE — apply to every cell:
1. CAUSE-EFFECT ONLY. Every recommendation must state what the data shows AND what the team should do about it.
   Pattern: [what the data shows] → [specific action]
   Example: "Static posts averaged 0.4% ER vs Reels at 1.8% ER → reduce Static-only weeks"
2. NO VAGUE LANGUAGE. Phrases like "consider reviewing", "explore opportunities", "look into" are banned.
   Every phrase must be a clear instruction or a specific observation.
3. NO HYPE. Do not use: "massive", "explosive", "incredible", "amazing", "huge surge".
4. CONSERVATIVE ON STOP. For a bank, promotions, product content, brand campaigns are mandatory.
   Only recommend STOP for a very specific FORMAT or EXECUTION STYLE with clear data evidence of underperformance
   AND a proven better alternative in the data. If unsure, write: "No change, monitor performance".
5. CELL FORMAT: short phrases only (max 15 words per cell). Not full paragraphs.

HOW TO READ THE DATA:
- top5_posts: titles of BEST performing content → infer themes (e.g. "[Theme A]", "[Theme B]" based strictly on the actual titles)
- bot5_posts: titles of WORST performing content → infer what execution styles to STOP or PAUSE
- format_performance: which formats (Reel, Video, Static, Carousel) drove highest vs lowest avg ER

HOW TO WRITE EACH CELL:
- STOP: Specific underperforming FORMAT or EXECUTION STYLE only. Default: "No change, monitor performance"
- PAUSE: Formats/themes with inconsistent ER (high er_spread). If none, write: "No pause required"
- CONTINUE: Proven high-ER themes and formats inferred from top5. Short phrases, comma-separated.
- ENHANCE: High-potential themes/formats in top performers but underused (few posts, high best_er).

Return ONLY valid JSON, no markdown, no code fences:
{{
  "platform_strategy": {{
    "Facebook":  {{"stop": "...", "pause": "...", "continue": "...", "enhance": "..."}},
    "Instagram": {{"stop": "...", "pause": "...", "continue": "...", "enhance": "..."}},
    "TikTok":    {{"stop": "...", "pause": "...", "continue": "...", "enhance": "..."}},
    "YouTube":   {{"stop": "...", "pause": "...", "continue": "...", "enhance": "..."}},
    "LinkedIn":  {{"stop": "...", "pause": "...", "continue": "...", "enhance": "..."}}
  }},
  "key_takeaways": ["...", "...", "...", "...", "..."]
}}

Key takeaways rules — exactly 5 items, one per platform:
- Each takeaway MUST follow cause-effect structure:
  [What the data showed for this platform this period] + [therefore, the specific next action]
- Formula: "[Platform]'s [format/theme] [performed at X% ER / declined / outperformed], [because/supported by] [data evidence]; the next step is to [specific action]."
- Reference the platform's avg ER% and at least one format or theme proven in the data.
- ONE complete professional sentence per takeaway. Written for senior management.
- BANNED: vague directives like "should explore", "consider investing", "look into possibilities".
- BANNED: takeaways that only describe a metric without a forward-looking action.
- DO NOT name specific post titles."""

    # ── Prompt 2: Key Learnings ──────────────────────────────────────────────────
    prompt2 = f"""You are a senior social media strategist producing a board-level report for CIMB Bank Malaysia.
Period: {period_label}
Platform ER ranking: {er_rank_str}

Per-platform analytics (top/bottom post titles + format breakdown):
{data_str}

TASK: Write 4 KEY LEARNINGS.

===========================================================================
STYLE GUIDE — study these examples before writing
===========================================================================

You are writing for a strategist audience, not a data analyst. The goal:
  - Title = The insight in a punchy cause-effect phrase.
  - Description = Explain WHY the content worked. Reference the creative mechanic or content format.
    You may cite 1-2 ER numbers to ground it, but do NOT make the description a list of numbers.
  - Action = One bold directive the content team can execute NEXT MONTH. Specific. Concrete. No hedging.

─── EXAMPLE of GOOD writing (Use as structure template, DO NOT copy these themes) ───

Title: "[Content Theme/Mechanic] is a repeatable engagement driver"
Description: "Content built around [Specific execution style inferred from top posts] performed
  consistently across [Platform A] and [Platform B], with ER ranging from [X]% to [Y]% on [Platform A].
  This shows that [Audience Insight] works when delivered through a recognisable recurring format
  and [Specific delivery style] — not one-off posts."
Action: "Turn high-performing [Theme] topics into recurring series covering [Sub-topic 1], [Sub-topic 2],
  and [Sub-topic 3] — run across [Platform A] and [Platform B] with a consistent format."

Title: "[Creative Format] boosted engagement through a simple participation loop."
Description: "Content that asked audiences to [Specific action, e.g., interact, vote, or share] drove higher comment
  and share rates across [Platform]. The mechanic works because it turns passive viewing into active participation,
  reducing scroll-past behaviour."
Action: "Build more [Specific interactive format] around timely moments or [Specific theme]."

Title: "Promotional content needs utility or a mechanic to work"
Description: "Generic promotional posts consistently underperformed across [Platform A], [Platform B] and [Platform C],
  falling below [X]% ER, while promo posts with a [Specific element, e.g., reward mechanic, challenge] performed significantly better."
Action: "Turn product posts into [Specific engaging format].
  Generic product pushes should be reduced or rebuilt with a participation hook."

─── EXAMPLE of BAD writing ───

Title: "[Generic format] outperforms" (too vague)
Description: "[Platform A] and [Platform B] showed higher engagement rates ([X]% and [Y]% avg ER) compared to other
  platforms, supported by [Format] content performance ([Z]% avg ER on [Platform A] and [W]% avg ER on [Platform B]).
  This confirms the effectiveness of [Format]-led content in driving engagement. The strong performance of [Format]
  content on these platforms is likely due to the high engagement rates of [Format] posts ([V]% avg ER on
  [Platform A] and [U]% avg ER on [Platform B])." → TOO MANY NUMBERS. REPEATS THE SAME STAT. NO MECHANIC EXPLAINED.
Action: "Prioritise [Format] format across [Platform A] and [Platform B], targeting ≥3 posts per week, to sustain the
  [X]% avg ER proven this period." → TOO MECHANICAL. Does not describe a content mechanic or creative approach.

===========================================================================
HOW TO USE THE DATA:
  - Look at top5_posts titles across ALL platforms to infer WHAT CONTENT THEMES or CREATIVE MECHANICS worked.
    (Do not quote post titles directly — describe the format or mechanic you can infer from them.)
  - Look at bot5_posts to infer what execution approaches failed.
  - Use format_performance to understand which format types drove the patterns you're describing.
  - Use ER numbers SPARINGLY — one or two per description to ground the insight, not to fill sentences.
===========================================================================

CROSS-PLATFORM RULE: Each learning MUST reference 2+ platforms. Not a single-platform observation.
TOPIC VARIETY: Cover 4 different themes — e.g. content mechanic, format type, content theme, organic vs paid, reach vs engagement.

Return ONLY valid JSON, no markdown, no code fences:
{{
  "key_learnings": [
    {{"number": 1, "title": "...", "description": "...", "action": "..."}},
    {{"number": 2, "title": "...", "description": "...", "action": "..."}},
    {{"number": 3, "title": "...", "description": "...", "action": "..."}},
    {{"number": 4, "title": "...", "description": "...", "action": "..."}}
  ]
}}

Rules:
- Exactly 4 learnings on 4 different themes.
- Description: 2-3 sentences. Explain the creative mechanic or content approach. Max 2 ER numbers cited.
- Action: ONE directive. Strong imperative verb. Describes what content to make, not what metric to hit.
- DO NOT name specific post titles.
- DO NOT write a learning about only one platform.
- BANNED in action: 'should identify', 'consider exploring', 'look into', 'the focus should be on finding'.
- BANNED in description: hype words (massive, explosive, incredible), excessive number repetition."""

    # ── Call Groq (with pause between calls to avoid free-tier TPM rate limit) ───
    import time
    strategy_result = _call_groq(api_key, prompt1, max_tokens=2500)
    if "error" in strategy_result and "429" in str(strategy_result.get("error", "")):
        return {"error": "Groq rate limit hit on first call. Please wait 30 seconds and try again."}
    time.sleep(15)   # wait 15s so TPM window resets before second call
    learnings_result = _call_groq(api_key, prompt2, max_tokens=2500)
    if "error" in learnings_result and "429" in str(learnings_result.get("error", "")):
        return {"error": "Groq rate limit hit on second call. Please wait 30 seconds and try again."}

    if "error" in strategy_result:
        return {"error": f"Strategy prompt failed: {strategy_result['error']}"}
    if "error" in learnings_result:
        return {"error": f"Learnings prompt failed: {learnings_result['error']}"}

    return {
        "period":            period_label,
        "platform_strategy": strategy_result.get("platform_strategy", {}),
        "key_takeaways":     strategy_result.get("key_takeaways", []),
        "key_learnings":     learnings_result.get("key_learnings", []),
    }


@app.get("/api/wip-data")
def get_wip_data(
    sheet_url: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    url = sheet_url
    if "/edit" in url:
        url = url.split("/edit")[0] + "/export?format=xlsx"
    elif not url.endswith("export?format=xlsx"):
        if url.endswith("/"):
            url += "export?format=xlsx"
        else:
            url += "/export?format=xlsx"

    try:
        xl = pd.ExcelFile(url)
    except Exception as e:
        return {"error": f"Could not read Google Sheet: {e}"}

    def _num(row, *keys):
        for k in keys:
            v = row.get(k)
            if pd.isna(v):
                continue
            try:
                f = float(v)
                if not math.isnan(f):
                    return f
            except:
                pass
        return 0.0

    def _in_range(dt):
        if pd.isna(dt):
            return False
        try:
            dt_ts = pd.to_datetime(dt)
        except:
            return False
        if start_date and dt_ts < pd.to_datetime(start_date):
            return False
        if end_date:
            end_dt = pd.to_datetime(end_date)
            if end_dt.time() == pd.Timestamp('00:00:00').time():
                end_dt = end_dt + pd.Timedelta(days=1, seconds=-1)
            if dt_ts > end_dt:
                return False
        return True

    result = {}

    if "Raw_FB" in xl.sheet_names:
        fb = xl.parse("Raw_FB")
        fb_dates = pd.to_datetime(fb.get("Publish time"), errors="coerce")
        posts, total_reach, total_eng, total_views, er_list = 0, 0.0, 0.0, 0.0, []
        for idx, row in fb.iterrows():
            pub_time = row.get("Publish time")
            if pd.isna(pub_time):
                continue
            if not _in_range(fb_dates[idx]):
                continue
            posts += 1
            total_reach += _num(row, "Reach", "Lifetime Post Total Reach")
            views = _num(row, "Views")
            eng = _num(row, "Reactions, comments and shares")
            total_eng += eng
            total_views += views
            if views > 0:
                er_list.append(eng / views * 100)
        result["Facebook"] = {
            "posts_count": posts,
            "total_reach": round(total_reach),
            "total_engagement": round(total_eng),
            "total_video_views": round(total_views),
            "avg_engagement_rate": round(sum(er_list)/len(er_list), 2) if er_list else 0.0,
        }

    if "Raw_IG" in xl.sheet_names:
        ig = xl.parse("Raw_IG")
        ig_dates = pd.to_datetime(ig.get("Publish time"), errors="coerce")
        posts, total_reach, total_eng, total_views, er_list = 0, 0.0, 0.0, 0.0, []
        for idx, row in ig.iterrows():
            pub_time = row.get("Publish time")
            if pd.isna(pub_time):
                continue
            if not _in_range(ig_dates[idx]):
                continue
            posts += 1
            total_reach += _num(row, "Reach")
            views = _num(row, "Views")
            eng = _num(row, "Likes") + _num(row, "Comments") + _num(row, "Shares") + _num(row, "Saves")
            total_eng += eng
            total_views += views
            if views > 0:
                er_list.append(eng / views * 100)
        result["Instagram"] = {
            "posts_count": posts,
            "total_reach": round(total_reach),
            "total_engagement": round(total_eng),
            "video_views": round(total_views),
            "avg_engagement_rate": round(sum(er_list)/len(er_list), 2) if er_list else 0.0,
        }

    if "Raw_Youtube" in xl.sheet_names:
        yt = xl.parse("Raw_Youtube")
        yt_dates = pd.to_datetime(yt.get("Video publish time"), errors="coerce")
        total_views, total_imp, total_wt = 0.0, 0.0, 0.0
        for idx, row in yt.iterrows():
            pub_time = row.get("Video publish time")
            if pd.isna(pub_time):
                continue
            if not _in_range(yt_dates[idx]):
                continue
            total_views += _num(row, "Views")
            total_imp += _num(row, "Impressions")
            total_wt += _num(row, "Watch time (hours)")
        result["YouTube"] = {
            "total_views": round(total_views),
            "impressions": round(total_imp),
            "watch_time_hours": round(total_wt, 1),
        }
    return result


@app.get("/api/wip-summary")
def get_wip_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Return WIP-style aggregated metrics from the database for each platform."""
    df = get_filtered_data(start_date, end_date)

    result = {}
    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube']

    for platform in platforms:
        pdf = df[df['platform'] == platform]
        if pdf.empty:
            continue

        posts_count = len(pdf)
        total_reach = float(pdf['reach'].sum())
        total_engagement = float(pdf['engagement'].sum())
        total_views = float(pdf['views'].sum())
        avg_er = float(pdf['engagement_rate'].mean()) if posts_count > 0 else 0.0
        total_likes = float(pdf['likes'].sum())
        total_comments = float(pdf['comments'].sum()) if 'comments' in pdf else 0.0
        total_shares = float(pdf['shares'].sum()) if 'shares' in pdf else 0.0
        total_favorites = float(pdf['favorites'].sum()) if 'favorites' in pdf else 0.0
        total_reposts = float(pdf['reposts'].sum()) if 'reposts' in pdf else 0.0
        total_impressions = float(pdf['impressions'].sum()) if 'impressions' in pdf else 0.0
        total_watch_time = float(pdf['watch_time_hours'].sum()) if 'watch_time_hours' in pdf else 0.0

        result[platform] = {
            "posts_count": posts_count,
            "total_reach": round(total_reach),
            "total_engagement": round(total_engagement),
            "total_views": round(total_views),
            "avg_engagement_rate": round(avg_er, 2),
            "total_likes": round(total_likes),
            "total_comments": round(total_comments),
            "total_shares": round(total_shares),
            "total_favorites": round(total_favorites),
            "total_reposts": round(total_reposts),
            "impressions": round(total_impressions),
            "watch_time_seconds": round(total_watch_time * 3600),
        }

    return result


# ── Helper: call Groq for chat with history ───────────────────────────────────
def _call_groq_chat(api_key: str, messages: List[Dict[str, str]], max_tokens: int = 3000):
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    # Using the best models for conversational / reporting stuff
    GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error = None
    for model in GROQ_MODELS:
        try:
            payload = {
                "model": model, 
                "messages": messages,
                "temperature": 0.3, 
                "max_tokens": max_tokens
            }
            resp = http_requests.post(GROQ_URL, headers=headers, json=payload, timeout=90)
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                return raw
            elif resp.status_code in (404, 400):
                last_error = resp.text
                continue
            else:
                return {"error": f"Groq API error {resp.status_code}: {resp.text}"}
        except Exception as e:
            last_error = str(e)
            continue
    return {"error": f"No Groq model succeeded. Last error: {last_error}"}

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    active_tab: Optional[str] = None
    executive_summary: Optional[Dict[str, Any]] = None
    strategy_data: Optional[Dict[str, Any]] = None

@app.post("/api/chat")
def chat_with_data(request: ChatRequest):
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"error": "GROQ_API_KEY not set."}

    df = get_filtered_data(request.start_date, request.end_date)
    if df.empty:
        return {"error": "No data available for the selected period."}

    # Build a summarized context of the dataset for the AI
    # Reusing logic from the strategy endpoint for a rich context
    PLATS = ["Facebook", "Instagram", "TikTok", "YouTube", "LinkedIn"]
    plat_stats = {}
    
    def _r(v, n=2): return round(float(v), n) if v is not None else 0
    
    for plat in PLATS:
        pdf = df[df["platform"] == plat]
        if pdf.empty: continue
        
        all_er = _r(pdf["engagement_rate"].mean())
        
        fmt_rows = []
        if "format" in pdf.columns:
            for fmt, grp in pdf.groupby("format"):
                fmt = str(fmt).strip()
                if not fmt or fmt == "nan" or len(grp) == 0: continue
                fmt_rows.append({
                    "format": fmt,
                    "posts": len(grp),
                    "avg_er": _r(grp["engagement_rate"].mean()),
                })
                
        # Top 5 and bottom 5 posts for context
        title_col = "title" if "title" in pdf.columns else None
        def _title(row):
            t = str(row.get(title_col, "") or "").strip() if title_col else ""
            return t[:100] if t and t != "nan" else "(no title)"
            
        top5 = pdf.sort_values("engagement_rate", ascending=False).head(5)
        bot5 = pdf[pdf["engagement_rate"] > 0].sort_values("engagement_rate").head(5)
        
        plat_stats[plat] = {
            "total_posts": len(pdf),
            "avg_er": all_er,
            "avg_reach": int(pdf["reach"].mean()) if not pdf.empty else 0,
            "format_performance": fmt_rows,
            "top5_posts": [{"er": _r(r["engagement_rate"]), "title": _title(r)} for _, r in top5.iterrows()],
            "bot5_posts": [{"er": _r(r["engagement_rate"]), "title": _title(r)} for _, r in bot5.iterrows()],
        }

    data_str = json.dumps(plat_stats, indent=2)
    
    period_label = f"{request.start_date or 'the beginning'} to {request.end_date or 'present'}"

    system_prompt = f"""You are an expert Social Media Data Analyst for CIMB Bank Malaysia. 
Your job is to answer the user's questions accurately based ONLY on the data provided below.
If the data does not contain the answer, say "I don't have enough data to answer that."

Period: {period_label}

DATASET CONTEXT (Aggregated Stats and Top/Bottom Posts):
{data_str}
"""

    if request.active_tab:
        system_prompt += f"\nCURRENT DASHBOARD SECTION: The user is currently looking at the '{request.active_tab}' tab.\n"
        if request.active_tab == 'executive' and request.executive_summary:
            system_prompt += f"Here is the AI-generated Executive Summary currently on their screen:\n{json.dumps(request.executive_summary, indent=2)}\n"
            system_prompt += "If the user asks to rewrite, adjust, or change the executive summary, provide the revised version in your response.\n"
        elif request.active_tab in ['strategy', 'learnings'] and request.strategy_data:
            system_prompt += f"Here is the AI-generated Strategy/Learnings data currently on their screen:\n{json.dumps(request.strategy_data, indent=2)}\n"
            system_prompt += "If the user asks to modify these strategies or learnings, provide the revised version in your response.\n"

    system_prompt += """
Guidelines:
- Be concise, professional, and helpful.
- When referencing posts, describe them based on their titles.
- Use markdown for formatting (bolding, lists).
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add history
    for msg in request.history:
        # Groq allows role: 'user' or 'assistant' (or 'system')
        if msg.role in ["user", "assistant"]:
            messages.append({"role": msg.role, "content": msg.content})
            
    # Add current message
    messages.append({"role": "user", "content": request.message})
    
    response = _call_groq_chat(api_key, messages)
    
    if isinstance(response, dict) and "error" in response:
        return {"error": response["error"]}
        
    return {"reply": response}


# ── Export PPTX Platform Highlights ──────────────────────────────────────────
from slide_generator import generate_platform_highlights_slide
import json

@app.get("/api/export-platform-highlights")
def export_platform_highlights(start_date: str = Query(""), end_date: str = Query("")):
    if not start_date or start_date == "undefined" or not end_date or end_date == "undefined":
        raise HTTPException(status_code=400, detail="start_date and end_date are required to calculate previous period trends.")
        
    df_curr = get_filtered_data(start_date, end_date)
    
    try:
        dt_start = pd.to_datetime(start_date)
        dt_end = pd.to_datetime(end_date)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
        
    delta = dt_end - dt_start
    prev_end = dt_start - pd.Timedelta(days=1)
    prev_start = prev_end - delta
    
    df_prev = get_filtered_data(prev_start.strftime('%Y-%m-%d'), prev_end.strftime('%Y-%m-%d'))
    
    prev_month_label = prev_end.strftime('%b %y')
    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']
    
    api_key = os.getenv("GROQ_API_KEY", "")
    
    platforms_data = {}
    prompt_data = ""
    
    for platform in platforms:
        curr_pdf = df_curr[df_curr['platform'] == platform]
        prev_pdf = df_prev[df_prev['platform'] == platform]
        
        c_posts = len(curr_pdf)
        p_posts = len(prev_pdf)

        c_reach = float(curr_pdf['reach'].mean()) if c_posts > 0 else 0
        p_reach = float(prev_pdf['reach'].mean()) if p_posts > 0 else 0

        c_er = float(curr_pdf['engagement_rate'].mean()) if c_posts > 0 else 0
        p_er = float(prev_pdf['engagement_rate'].mean()) if p_posts > 0 else 0
        
        platforms_data[platform] = {
            "posts": c_posts,
            "prev_posts": p_posts,
            "avg_reach": c_reach,
            "prev_avg_reach": p_reach,
            "avg_er": c_er,
            "prev_avg_er": p_er,
            "insight": "No data available."
        }
        
        if c_posts > 0 or p_posts > 0:
            current_count = f"{c_posts} posts"
            previous_count = f"{p_posts} posts"
            prompt_data += f"- {platform}:\n"
            prompt_data += f"  Current: {current_count}, {c_reach:,.0f} avg reach, {c_er:.2f}% avg ER\n"
            prompt_data += f"  Previous: {previous_count}, {p_reach:,.0f} avg reach, {p_er:.2f}% avg ER\n\n"

    if api_key and prompt_data:
        prompt = f"""You are a professional social media analyst. Based on the following data, write exactly 1 to 2 sentences summarizing the performance for EACH platform. 
Focus on the trend (e.g. "reach surged despite fewer posts" or "steady engagement"). Be concise, professional, and analytical. Do not use hashtags or emojis.

Data:
{prompt_data}

Return ONLY a valid JSON object where the keys are the platform names and the values are the 1-2 sentence insights.
Example: {{"Facebook": "Insight...", "Instagram": "Insight..."}}"""
        groq_resp = _call_groq(api_key, prompt, max_tokens=1000)
        if "error" not in groq_resp:
            try:
                content = groq_resp["content"].strip()
                if content.startswith("```json"): content = content[7:]
                if content.startswith("```"): content = content[3:]
                if content.endswith("```"): content = content[:-3]
                
                insights_json = json.loads(content.strip())
                for p, ins in insights_json.items():
                    if p in platforms_data:
                        platforms_data[p]["insight"] = ins
            except Exception as e:
                for p in platforms:
                    platforms_data[p]["insight"] = f"AI JSON Error: {e}"
        else:
            for p in platforms:
                platforms_data[p]["insight"] = f"Error: {groq_resp['error']}"

    pptx_io = generate_platform_highlights_slide(platforms_data, prev_month_label)
    
    return StreamingResponse(
        pptx_io,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename=Platform_Highlights_{dt_start.strftime('%b')}.pptx"}
    )
