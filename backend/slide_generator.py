from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import io

def _set_cell_text(cell, text, bold=False, color=None, size=Pt(11), align=PP_ALIGN.CENTER):
    text_frame = cell.text_frame
    text_frame.clear()
    p = text_frame.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.bold = bold
    p.font.size = size
    if color:
        p.font.color.rgb = color
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE

def _add_subtext(cell, text, color=RGBColor(100, 100, 100), size=Pt(9)):
    p = cell.text_frame.add_paragraph()
    p.text = text
    p.alignment = PP_ALIGN.CENTER
    p.font.color.rgb = color
    p.font.size = size

def generate_platform_highlights_slide(platforms_data, prev_month_label):
    """
    platforms_data is a dict where keys are platform names, and values are dicts with:
      posts, prev_posts, avg_reach, prev_avg_reach, avg_er, prev_avg_er, insight
    """
    prs = Presentation()
    # 16:9 aspect ratio
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    slide_layout = prs.slide_layouts[5] # Title only
    slide = prs.slides.add_slide(slide_layout)
    
    # Set Title
    title_shape = slide.shapes.title
    title_shape.text = "Platform Highlights"
    title_shape.text_frame.paragraphs[0].font.color.rgb = RGBColor(192, 0, 0)
    title_shape.text_frame.paragraphs[0].font.size = Pt(36)
    title_shape.text_frame.paragraphs[0].font.bold = True
    title_shape.left = Inches(0.5)
    title_shape.top = Inches(0.3)
    
    # Table dimensions
    rows = 6
    cols = 6
    left = Inches(0.5)
    top = Inches(1.2)
    width = Inches(12.333)
    height = Inches(5.5)
    
    shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = shape.table
    
    # Column Widths
    table.columns[0].width = Inches(2.0) # Platform
    table.columns[1].width = Inches(1.5) # Followers
    table.columns[2].width = Inches(1.2) # Posts
    table.columns[3].width = Inches(1.5) # Avg Reach
    table.columns[4].width = Inches(1.2) # Avg ER
    table.columns[5].width = Inches(4.933) # Key Notes
    
    # Headers
    headers = ["Platform", "Followers", "Posts", "Avg Reach", "Avg ER", "Key Notes/Findings"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(192, 0, 0)
        align = PP_ALIGN.LEFT if i == 5 else PP_ALIGN.CENTER
        _set_cell_text(cell, h, bold=True, color=RGBColor(255, 255, 255), size=Pt(14), align=align)
    
    platforms = ["Facebook", "Instagram", "TikTok", "YouTube", "LinkedIn"]
    
    for idx, platform in enumerate(platforms):
        row_idx = idx + 1
        data = platforms_data.get(platform, {})
        
        # Alternate row background
        bg_color = RGBColor(245, 245, 245) if row_idx % 2 == 1 else RGBColor(255, 255, 255)
        for c in range(6):
            cell = table.cell(row_idx, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg_color
            
        # 1. Platform (Mock black box styling for platform name like screenshot)
        p_cell = table.cell(row_idx, 0)
        p_cell.fill.solid()
        p_cell.fill.fore_color.rgb = RGBColor(0, 0, 0)
        _set_cell_text(p_cell, platform, bold=True, color=RGBColor(255, 255, 255), size=Pt(14))
        
        # 2. Followers (N/A for now since data not available)
        _set_cell_text(table.cell(row_idx, 1), "N/A", size=Pt(12))
        
        if data:
            # 3. Posts
            _set_cell_text(table.cell(row_idx, 2), f"{data.get('posts', 0):,}", size=Pt(12))
            _add_subtext(table.cell(row_idx, 2), f"({data.get('prev_posts', 0):,} in {prev_month_label})")
            
            # 4. Avg Reach
            _set_cell_text(table.cell(row_idx, 3), f"{data.get('avg_reach', 0):,.0f}", size=Pt(12))
            _add_subtext(table.cell(row_idx, 3), f"({data.get('prev_avg_reach', 0):,.0f} in {prev_month_label})")
            
            # 5. Avg ER
            _set_cell_text(table.cell(row_idx, 4), f"{data.get('avg_er', 0):.2f}%", size=Pt(12))
            _add_subtext(table.cell(row_idx, 4), f"({data.get('prev_avg_er', 0):.2f}% in {prev_month_label})")
            
            # 6. Key Notes (Left aligned)
            insight = data.get('insight', 'No data available for this platform.')
            _set_cell_text(table.cell(row_idx, 5), insight, size=Pt(10), align=PP_ALIGN.LEFT)
        else:
            # Empty rows if platform is missing
            for c in range(2, 6):
                _set_cell_text(table.cell(row_idx, c), "-", size=Pt(12))

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output
