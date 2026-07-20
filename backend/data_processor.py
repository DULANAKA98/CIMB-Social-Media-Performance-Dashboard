import pandas as pd
import numpy as np
import hashlib

def generate_id(platform_prefix, row, link, title, date, idx):
    """Generate a guaranteed unique ID immune to float precision loss."""
    unique_str = link
    if not unique_str or unique_str == 'nan':
        unique_str = f"{title}_{date}_{idx}"
    hash_val = hashlib.md5(str(unique_str).encode('utf-8')).hexdigest()[:16]
    return f"{platform_prefix}_{hash_val}"

def get_val(row, col, default=0):
    val = row.get(col)
    if pd.isna(val): return default
    try:
        return float(val)
    except:
        return default


def parse_platform_dates(values):
    """Parse raw platform export dates in month/day/year or ISO order."""
    return pd.to_datetime(values, errors='coerce', dayfirst=False, format='mixed')

def process_data(fb, ig, yt, tt, li=None, ig_story=None):
    unified_data = []
    
    # Facebook
    if not fb.empty:
        fb_dates = parse_platform_dates(fb.get('Publish time'))
        for idx, row in fb.iterrows():
            if pd.isna(row.get('Publish time')): continue
            reach = get_val(row, 'Reach', get_val(row, 'Lifetime Post Total Reach'))
            views = get_val(row, 'Views')
            
            reactions_etc = get_val(row, 'Reactions, comments and shares')
            comments = get_val(row, 'Comments')
            shares = get_val(row, 'Shares')
            likes = max(0, reactions_etc - comments - shares)
            
            total_eng = reactions_etc # Reactions + comments + shares
            
            organic_paid_val = str(row.get('Organic/Paid', '')).strip().lower()
            if organic_paid_val:
                is_organic = (organic_paid_val == 'organic')
            else:
                organic_reach = get_val(row, 'Reach from Organic posts')
                paid_reach = get_val(row, 'Lifetime Post Paid Reach')
                is_organic = (organic_reach > 0 and paid_reach == 0)
            
            title = str(row.get('Description', row.get('Post message', '')))
            if not title or title.strip() == 'nan':
                title = str(row.get('Title', ''))
            
            format_val = str(row.get('Post type', ''))
            if format_val == 'nan': format_val = 'Unknown'
            
            date_str = fb_dates[idx].isoformat() if pd.notna(fb_dates[idx]) else None
            link = str(row.get('Permalink', row.get('Link', '')))
            
            unified_data.append({
                'id': generate_id('fb', row, link, title, date_str, idx),
                'platform': 'Facebook',
                'format': format_val,
                'date': date_str,
                'title': title,
                'link': link,
                'reach': reach,
                'views': views,
                'engagement': total_eng,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'favorites': 0,
                'reposts': 0,
                'engagement_rate': (total_eng / reach * 100) if reach > 0 else 0,
                'is_organic': is_organic
            })
            
    # Instagram
    if not ig.empty:
        ig_dates = parse_platform_dates(ig.get('Publish time'))
        for idx, row in ig.iterrows():
            if pd.isna(row.get('Publish time')): continue
            reach = get_val(row, 'Reach')
            views = get_val(row, 'Views')
            likes = get_val(row, 'Likes')
            shares = get_val(row, 'Shares')
            comments = get_val(row, 'Comments')
            saves = get_val(row, 'Saves')
            total_eng = likes + comments + shares + saves
            
            organic_paid_val = str(row.get('Organic/Paid', '')).strip().lower()
            is_organic = (organic_paid_val == 'organic') if organic_paid_val else True

            format_val = str(row.get('Post type', ''))
            if format_val == 'nan': format_val = 'Unknown'

            date_str = ig_dates[idx].isoformat() if pd.notna(ig_dates[idx]) else None
            link = str(row.get('Permalink', ''))

            unified_data.append({
                'id': generate_id('ig', row, link, str(row.get('Description', '')), date_str, idx),
                'platform': 'Instagram',
                'format': format_val,
                'date': date_str,
                'title': str(row.get('Description', '')),
                'link': link,
                'reach': reach,
                'views': views,
                'engagement': total_eng,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'favorites': saves,
                'reposts': 0,
                'engagement_rate': (total_eng / reach * 100) if reach > 0 else 0,
                'is_organic': is_organic
            })

    # Instagram Stories (uploaded separately from Instagram posts)
    if ig_story is not None and not ig_story.empty:
        ig_story_dates = parse_platform_dates(ig_story.get('Publish time'))
        for idx, row in ig_story.iterrows():
            if pd.isna(row.get('Publish time')): continue
            reach = get_val(row, 'Reach')
            views = get_val(row, 'Views')
            likes = get_val(row, 'Likes')
            shares = get_val(row, 'Shares')
            replies = get_val(row, 'Replies')
            total_eng = likes + shares + replies

            organic_paid_val = str(row.get('Organic/Paid', '')).strip().lower()
            is_organic = (organic_paid_val == 'organic') if organic_paid_val else True

            date_str = ig_story_dates[idx].isoformat() if pd.notna(ig_story_dates[idx]) else None
            link = str(row.get('Permalink', ''))
            title_val = row.get('Description', '')
            title = '' if pd.isna(title_val) else str(title_val)
            source_format = str(row.get('Post type', '')).strip()
            format_val = 'IG Story' if source_format.lower() == 'ig story' else (source_format or 'IG Story')

            unified_data.append({
                'id': generate_id('ig_story', row, link, title, date_str, idx),
                'platform': 'Instagram',
                'format': format_val,
                'date': date_str,
                'title': title,
                'link': link,
                'reach': reach,
                'views': views,
                'engagement': total_eng,
                'likes': likes,
                'comments': replies,
                'shares': shares,
                'favorites': 0,
                'reposts': 0,
                'engagement_rate': (total_eng / reach * 100) if reach > 0 else 0,
                'is_organic': is_organic
            })
            
    # YouTube
    if not yt.empty:
        yt_dates = parse_platform_dates(yt.get('Video publish time'))
        for idx, row in yt.iterrows():
            if pd.isna(row.get('Video publish time')): continue
            views = get_val(row, 'Views')
            likes = get_val(row, 'Likes')
            comments = get_val(row, 'Comments added')
            shares = get_val(row, 'Shares')
            impressions = get_val(row, 'Impressions')
            watch_time = get_val(row, 'Watch time (hours)')
            total_eng = likes + comments + shares
            
            organic_paid_val = str(row.get('Organic/ Paid', row.get('Organic/Paid', ''))).strip().lower()
            is_organic = (organic_paid_val == 'organic') if organic_paid_val else True
            
            date_str = yt_dates[idx].isoformat() if pd.notna(yt_dates[idx]) else None
            link = f"https://youtube.com/watch?v={row.get('Content', '')}"

            unified_data.append({
                'id': generate_id('yt', row, link, str(row.get('Video title', '')), date_str, idx),
                'platform': 'YouTube',
                'format': 'Video',
                'date': date_str,
                'title': str(row.get('Video title', '')),
                'link': link,
                'reach': views,
                'views': views,
                'engagement': total_eng,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'favorites': 0,
                'reposts': 0,
                'impressions': impressions,
                'watch_time_hours': watch_time,
                'engagement_rate': (total_eng / views * 100) if views > 0 else 0,
                'is_organic': is_organic
            })
            
    # TikTok
    if not tt.empty:
        tt_dates = parse_platform_dates(tt.get('Post time'))
        for idx, row in tt.iterrows():
            if pd.isna(row.get('Post time')): continue
            views = get_val(row, 'Video views')
            if views < 10: continue
            
            likes = get_val(row, 'Likes')
            shares = get_val(row, 'Shares')
            comments = get_val(row, 'Comments')
            favorites = get_val(row, 'Add to Favorites')
            total_eng = likes + shares + comments + favorites
            
            organic_paid_val = str(row.get('Organic/Paid', '')).strip().lower()
            is_organic = (organic_paid_val == 'organic') if organic_paid_val else True
            
            date_str = tt_dates[idx].isoformat() if pd.notna(tt_dates[idx]) else None
            link = str(row.get('Video link', ''))

            unified_data.append({
                'id': generate_id('tt', row, link, str(row.get('Video title', '')), date_str, idx),
                'platform': 'TikTok',
                'format': 'Video',
                'date': date_str,
                'title': str(row.get('Video title', '')),
                'link': link,
                'reach': views, # TikTok Reach is essentially views
                'views': views,
                'engagement': total_eng,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'favorites': favorites,
                'reposts': 0,
                'engagement_rate': (total_eng / views * 100) if views > 0 else 0,
                'is_organic': is_organic
            })
            
    # LinkedIn
    if li is not None and not li.empty:
        li_dates = parse_platform_dates(li.get('Created date'))
        for idx, row in li.iterrows():
            if pd.isna(row.get('Created date')): continue
            impressions = get_val(row, 'Impressions')
            views = get_val(row, 'Views')
            likes = get_val(row, 'Likes')
            comments = get_val(row, 'Comments')
            reposts = get_val(row, 'Reposts')
            total_eng = likes + comments + reposts

            organic_paid_val = str(row.get('Organic/Paid', '')).strip().lower()
            is_organic = (organic_paid_val == 'organic') if organic_paid_val else True
            
            format_val = str(row.get('Content Type', ''))
            if format_val == 'nan': format_val = 'Unknown'

            date_str = li_dates[idx].isoformat() if pd.notna(li_dates[idx]) else None
            link = str(row.get('Post link', ''))

            unified_data.append({
                'id': generate_id('li', row, link, str(row.get('Post title', '')), date_str, idx),
                'platform': 'LinkedIn',
                'format': format_val,
                'date': date_str,
                'title': str(row.get('Post title', '')),
                'link': link,
                'reach': impressions,
                'views': views,
                'engagement': total_eng,
                'likes': likes,
                'comments': comments,
                'shares': 0,
                'favorites': 0,
                'reposts': reposts,
                'engagement_rate': (total_eng / impressions * 100) if impressions > 0 else 0,
                'is_organic': is_organic
            })

    df = pd.DataFrame(unified_data)
    df = df.replace({np.nan: None})
    return df.to_dict(orient='records')
