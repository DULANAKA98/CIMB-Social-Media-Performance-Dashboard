import re
import json

def fix_main():
    with open("backend/main.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # We want to keep everything before `    platforms = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn']`
    # around line 2004 where the bad edit started.
    # We can just split by "    return {\"reply\": response}" which is at line 2003.
    
    parts = content.split('    return {"reply": response}\n')
    good_content = parts[0] + '    return {"reply": response}\n'
    
    # Now append the correct export_platform_highlights
    new_endpoint = """

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
            prompt_data += f"- {platform}:\\n"
            prompt_data += f"  Current: {c_posts} posts, {c_reach:,.0f} avg reach, {c_er:.2f}% avg ER\\n"
            prompt_data += f"  Previous: {p_posts} posts, {p_reach:,.0f} avg reach, {p_er:.2f}% avg ER\\n\\n"

    if api_key and prompt_data:
        prompt = f\"\"\"You are a professional social media analyst. Based on the following data, write exactly 1 to 2 sentences summarizing the performance for EACH platform. 
Focus on the trend (e.g. "reach surged despite fewer posts" or "steady engagement"). Be concise, professional, and analytical. Do not use hashtags or emojis.

Data:
{prompt_data}

Return ONLY a valid JSON object where the keys are the platform names and the values are the 1-2 sentence insights.
Example: {{"Facebook": "Insight...", "Instagram": "Insight..."}}\"\"\"
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
"""
    
    with open("backend/main.py", "w", encoding="utf-8") as f:
        f.write(good_content + new_endpoint)

fix_main()
