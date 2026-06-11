import os

def append_endpoint():
    code = """

# ── Export PPTX Platform Highlights ──────────────────────────────────────────
from slide_generator import generate_platform_highlights_slide

@app.get("/api/export-platform-highlights")
def export_platform_highlights(start_date: str = Query(...), end_date: str = Query(...)):
    df_curr = get_filtered_data(start_date, end_date)
    
    # Calculate previous period
    dt_start = pd.to_datetime(start_date)
    dt_end = pd.to_datetime(end_date)
    delta = dt_end - dt_start
    prev_end = dt_start - pd.Timedelta(days=1)
    prev_start = prev_end - delta
    
    df_prev = get_filtered_data(prev_start.strftime('%Y-%m-%d'), prev_end.strftime('%Y-%m-%d'))
    
    prev_month_label = prev_end.strftime('%b %y')
    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']
    
    api_key = os.getenv("GROQ_API_KEY", "")
    
    platforms_data = {}
    
    for platform in platforms:
        curr_pdf = df_curr[df_curr['platform'] == platform]
        prev_pdf = df_prev[df_prev['platform'] == platform]
        
        c_posts = len(curr_pdf)
        p_posts = len(prev_pdf)
        
        c_reach = float(curr_pdf['reach'].mean()) if c_posts > 0 else 0
        p_reach = float(prev_pdf['reach'].mean()) if p_posts > 0 else 0
        
        c_er = float(curr_pdf['engagement_rate'].mean()) if c_posts > 0 else 0
        p_er = float(prev_pdf['engagement_rate'].mean()) if p_posts > 0 else 0
        
        insight = "No data available."
        
        if c_posts > 0 or p_posts > 0:
            if not api_key:
                insight = "GROQ_API_KEY not set. Cannot generate insights."
            else:
                prompt = f\"\"\"
You are a professional social media analyst. Write exactly 1 to 2 sentences summarizing the performance of {platform} based on the following data.
Current period ({dt_start.strftime('%b')}): {c_posts} posts, {c_reach:,.0f} avg reach, {c_er:.2f}% avg engagement rate.
Previous period ({prev_month_label}): {p_posts} posts, {p_reach:,.0f} avg reach, {p_er:.2f}% avg engagement rate.

Focus on the trend (e.g. "reach surged despite fewer posts" or "steady engagement"). Be concise, professional, and analytical. Do not use hashtags or emojis.
\"\"\"
                groq_resp = _call_groq(api_key, prompt, max_tokens=150)
                if "error" not in groq_resp:
                    insight = groq_resp["content"].strip()
                else:
                    insight = "Error generating insight."
        
        platforms_data[platform] = {
            "posts": c_posts,
            "prev_posts": p_posts,
            "avg_reach": c_reach,
            "prev_avg_reach": p_reach,
            "avg_er": c_er,
            "prev_avg_er": p_er,
            "insight": insight
        }
        
    pptx_io = generate_platform_highlights_slide(platforms_data, prev_month_label)
    
    return StreamingResponse(
        pptx_io,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename=Platform_Highlights_{dt_start.strftime('%b')}.pptx"}
    )
"""
    with open("backend/main.py", "a", encoding="utf-8") as f:
        f.write(code)

append_endpoint()
