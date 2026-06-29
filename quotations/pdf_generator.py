"""
CutFlow – PDF Report Engine
Generates industry-grade quotation and production PDFs using ReportLab.
Enhanced format with professional styling, product images, and detailed layouts.
"""
import io
from datetime import date
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, PageBreak, KeepTogether, Image, PageTemplate, Frame, NextPageTemplate
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Polygon, Circle, Group
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ── Font registration ─────────────────────────────────────────────────────────
# Base-14 Helvetica has no glyph for the Indian Rupee sign (₹ / U+20B9), so any
# ₹ used in this module (Rate/Amount columns, totals, etc.) renders as a black
# box. DejaVu Sans includes it. The font files are bundled inside this app
# (quotations/fonts/) rather than relying on OS-installed fonts, since system
# font availability differs across dev machines and servers. Registered under
# the same 'Helvetica*' family names already used everywhere in this file, so
# no other code in this module needs to change.
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


def _register_fonts():
    required = {
        'Helvetica': 'DejaVuSans.ttf',
        'Helvetica-Bold': 'DejaVuSans-Bold.ttf',
        'Helvetica-Oblique': 'DejaVuSans-Oblique.ttf',
        'Helvetica-BoldOblique': 'DejaVuSans-BoldOblique.ttf',
    }
    missing = [fn for fn in required.values() if not os.path.isfile(os.path.join(_FONT_DIR, fn))]
    if missing:
        raise RuntimeError(
            f"CutFlow PDF generator: missing bundled font file(s) {missing} in "
            f"'{_FONT_DIR}'. The ₹ symbol will render incorrectly without these. "
            f"Make sure quotations/fonts/ was deployed along with this file."
        )
    for family, filename in required.items():
        pdfmetrics.registerFont(TTFont(family, os.path.join(_FONT_DIR, filename)))


_register_fonts()

# ── Colour Palette ────────────────────────────────────────────────────────────
HEADER_GREY = colors.HexColor('#7F7F7F')
BORDER_GREY = colors.HexColor('#A0A0A0')
YELLOW_HIGHLIGHT = colors.HexColor('#FFFF00')
VIBRANT_CYAN = colors.HexColor('#00E5FF')
BLUE_TEXT = colors.HexColor('#0000FF')
TEXT_DARK = colors.HexColor('#000000')

DARK_BLUE = colors.HexColor('#1E3A5F')
MID_BLUE  = colors.HexColor('#2B5797')
LIGHT_BG  = colors.HexColor('#EDF2F7')
GOLD      = colors.HexColor('#C9922A')
RED_ACC   = colors.HexColor('#C0392B')
WHITE     = colors.white
GREY_TXT  = colors.HexColor('#4A5568')
GREY_LINE = colors.HexColor('#CBD5E0')

PAGE_W, PAGE_H = A4
LMARGIN = 15 * mm
RMARGIN = 15 * mm
TMARGIN = 15 * mm
BMARGIN = 15 * mm
CONTENT_W = PAGE_W - LMARGIN - RMARGIN

_POSITION_LABEL_TRANSLATION = {
    'outer_frame_top': 'FRAME_TOP',
    'outer_frame_bottom': 'FRAME_BOTTOM',
    'outer_frame_left': 'FRAME_LEFT',
    'outer_frame_right': 'FRAME_RIGHT',
    'shutter_vertical': 'SASH_LEFT',
    'shutter_horizontal': 'SASH_TOP',
    'interlock': 'INTERLOCK',
    'mullion': 'MULLION',
    'track': 'TRACK',
    'bead_horizontal': 'BEAD_TOP',
    'bead_vertical': 'BEAD_LEFT',
}


def _translate_position_code(code: str) -> str:
    if not code:
        return ''
    return _POSITION_LABEL_TRANSLATION.get(code.lower(), code.upper())


def get_super_quality_windows_logo():
    d = Drawing(120, 35)
    icon = Group()
    icon.add(Rect(2, 0, 20, 20, fillColor=colors.HexColor('#E0E0E0'), strokeColor=colors.HexColor('#7F7F7F'), strokeWidth=1))
    icon.add(Line(12, 0, 12, 20, strokeColor=colors.HexColor('#7F7F7F'), strokeWidth=1))
    icon.add(Line(2, 10, 22, 10, strokeColor=colors.HexColor('#7F7F7F'), strokeWidth=1))
    icon.add(Polygon([2, 20, 12, 29, 22, 20], fillColor=colors.HexColor('#E0E0E0'), strokeColor=colors.HexColor('#7F7F7F'), strokeWidth=1))
    d.add(icon)
    
    d.add(String(26, 17, "SUPER QUALITY", fontName="Helvetica-Bold", fontSize=9.5, fillColor=colors.HexColor('#7F7F7F')))
    d.add(String(26, 5, "WINDOWS", fontName="Helvetica-Bold", fontSize=13, fillColor=colors.HexColor('#E65100')))
    return d


def draw_window_diagram(item):
    W = item.width
    H = item.height
    ref = (item.reference or '').upper()
    desc = (item.description or '').upper()
    sys_cat = item.system.category
    
    dw = 135
    dh = 135
    d = Drawing(dw, dh)
    
    vx = 22
    vy = 18
    vw = 90
    vh = 90
    
    scale = min(vw / W, vh / H)
    w_px = W * scale
    h_px = H * scale
    
    x0 = vx + (vw - w_px) / 2
    y0 = vy + (vh - h_px) / 2
    
    glass_color = colors.HexColor('#00E5FF')
    frame_color = colors.HexColor('#7F7F7F')
    dimension_color = colors.HexColor('#FF0000')
    text_color = colors.HexColor('#000000')
    blue_text = colors.HexColor('#0000FF')
    
    if 'W1' in ref or 'W1' in desc:
        top_h = 400 * scale
        bot_h = 1200 * scale
        
        # Glass Top
        d.add(Rect(x0, y0 + bot_h, w_px, top_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + w_px/2, y0 + bot_h + top_h/2 - 3, "Fix O", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        
        # Glass Bottom Left (600mm width)
        bl_w = (W/2) * scale
        d.add(Rect(x0, y0, bl_w, bot_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + bl_w/2, y0 + bot_h/2 - 3, "Left", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0, y0 + bot_h, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0, y0, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        # Glass Bottom Right
        d.add(Rect(x0 + bl_w, y0, bl_w, bot_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + bl_w + bl_w/2, y0 + bot_h/2 - 3, "Right", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0 + w_px, y0 + bot_h, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0 + w_px, y0, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        # Dimension annotations
        dim_y = y0 + h_px + 6
        d.add(Line(x0, dim_y, x0 + w_px, dim_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0, dim_y - 2, x0, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + bl_w, dim_y - 2, x0 + bl_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px, dim_y - 2, x0 + w_px, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(x0 + bl_w/2, dim_y + 2, "600", fontName="Helvetica", fontSize=6.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + bl_w + bl_w/2, dim_y + 2, "600", fontName="Helvetica", fontSize=6.5, textAnchor="middle", fillColor=dimension_color))
        
        dim_x = x0 - 6
        d.add(Line(dim_x, y0, dim_x, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0, dim_x + 2, y0, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + bot_h, dim_x + 2, y0 + bot_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + h_px, dim_x + 2, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(dim_x - 2, y0 + bot_h/2 - 2, "1200", fontName="Helvetica", fontSize=6.5, textAnchor="end", fillColor=dimension_color))
        d.add(String(dim_x - 2, y0 + bot_h + top_h/2 - 2, "400", fontName="Helvetica", fontSize=6.5, textAnchor="end", fillColor=dimension_color))
        
    elif 'W2' in ref or 'W2' in desc:
        bay_y = y0 + h_px * 0.72
        cx1 = x0 + w_px * 0.3
        cx2 = x0 + w_px * 0.7
        cy = bay_y
        lx = cx1 - 18
        ly = cy - 18
        rx = cx2 + 18
        ry = cy - 18
        
        d.add(Line(lx, ly, cx1, cy, strokeColor=colors.black, strokeWidth=1.2))
        d.add(Line(cx1, cy, cx2, cy, strokeColor=colors.black, strokeWidth=1.2))
        d.add(Line(cx2, cy, rx, ry, strokeColor=colors.black, strokeWidth=1.2))
        
        d.add(String((lx+cx1)/2 - 5, (ly+cy)/2 + 2, "635", fontName="Helvetica", fontSize=5.5, fillColor=dimension_color))
        d.add(String((cx1+cx2)/2, cy + 3, "1100", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String((cx2+rx)/2 + 5, (ry+cy)/2 + 2, "635", fontName="Helvetica", fontSize=5.5, fillColor=dimension_color))
        
        d.add(String(cx1 + 2, cy - 8, "135°", fontName="Helvetica", fontSize=5.5, fillColor=dimension_color))
        d.add(String(cx2 - 12, cy - 8, "135°", fontName="Helvetica", fontSize=5.5, fillColor=dimension_color))
        
        d.add(Line(lx, ly - 8, rx, ly - 8, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(lx, ly - 10, lx, ly - 6, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(rx, ly - 10, rx, ly - 6, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String((lx+rx)/2, ly - 15, "1995 (-2)", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        
        elev_h = h_px * 0.48
        elev_y = y0
        trans_h = elev_h * 0.3
        sash_h = elev_h * 0.7
        
        d.add(Rect(x0, elev_y + sash_h, w_px, trans_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + w_px/2, elev_y + sash_h + trans_h/2 - 2, "Top H", fontName="Helvetica-Bold", fontSize=6, textAnchor="middle", fillColor=text_color))
        
        s1_w = w_px * 0.25
        s2_w = w_px * 0.5
        
        d.add(Rect(x0, elev_y, s1_w, sash_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + s1_w/2, elev_y + sash_h/2 - 2, "Left", fontName="Helvetica-Bold", fontSize=6, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0, elev_y + sash_h, x0 + s1_w, elev_y + sash_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0, elev_y, x0 + s1_w, elev_y + sash_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        d.add(Rect(x0 + s1_w, elev_y, s2_w, sash_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + s1_w + s2_w/2, elev_y + sash_h/2 - 2, "FIXED", fontName="Helvetica-Bold", fontSize=6, textAnchor="middle", fillColor=text_color))
        
        d.add(Rect(x0 + s1_w + s2_w, elev_y, s1_w, sash_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + s1_w + s2_w + s1_w/2, elev_y + sash_h/2 - 2, "Right", fontName="Helvetica-Bold", fontSize=6, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0 + w_px, elev_y + sash_h, x0 + s1_w + s2_w, elev_y + sash_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0 + w_px, elev_y, x0 + s1_w + s2_w, elev_y + sash_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        dim_y = elev_y + elev_h + 4
        d.add(Line(x0, dim_y, x0 + w_px, dim_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0, dim_y - 2, x0, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + s1_w, dim_y - 2, x0 + s1_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + s1_w + s2_w, dim_y - 2, x0 + s1_w + s2_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px, dim_y - 2, x0 + w_px, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(x0 + s1_w/2, dim_y + 2, "535", fontName="Helvetica", fontSize=5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + s1_w + s2_w/2, dim_y + 2, "1100", fontName="Helvetica", fontSize=5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + s1_w + s2_w + s1_w/2, dim_y + 2, "635", fontName="Helvetica", fontSize=5, textAnchor="middle", fillColor=dimension_color))
        
        dim_x = x0 - 6
        d.add(Line(dim_x, elev_y, dim_x, elev_y + elev_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, elev_y, dim_x + 2, elev_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, elev_y + sash_h, dim_x + 2, elev_y + sash_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, elev_y + elev_h, dim_x + 2, elev_y + elev_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(dim_x - 2, elev_y + sash_h/2 - 2, "900", fontName="Helvetica", fontSize=5, textAnchor="end", fillColor=dimension_color))
        d.add(String(dim_x - 2, elev_y + sash_h + trans_h/2 - 2, "400", fontName="Helvetica", fontSize=5, textAnchor="end", fillColor=dimension_color))

    elif 'W3' in ref or 'W3' in desc:
        bot_h = 1400 * scale
        top_h = 600 * scale
        bl_w = w_px / 2
        
        d.add(Rect(x0, y0, bl_w, bot_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + bl_w/2, y0 + bot_h/2 - 3, "LTurn", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0, y0 + bot_h, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0, y0, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        d.add(Rect(x0 + bl_w, y0, bl_w, bot_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + bl_w + bl_w/2, y0 + bot_h/2 - 3, "RTurn", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0 + w_px, y0 + bot_h, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0 + w_px, y0, x0 + bl_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        s_w = 300 * scale
        d.add(Polygon([
            x0, y0 + bot_h,
            x0 + w_px, y0 + bot_h,
            x0 + w_px - s_w, y0 + h_px,
            x0 + s_w, y0 + h_px
        ], fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + w_px/2, y0 + bot_h + top_h/2 - 3, "FIXED", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        
        dim_y = y0 + h_px + 6
        d.add(Line(x0, dim_y, x0 + w_px, dim_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0, dim_y - 2, x0, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + s_w, dim_y - 2, x0 + s_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px/2, dim_y - 2, x0 + w_px/2, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px - s_w, dim_y - 2, x0 + w_px - s_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px, dim_y - 2, x0 + w_px, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        
        d.add(String(x0 + s_w/2, dim_y + 2, "300", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + s_w + (bl_w - s_w)/2, dim_y + 2, "350", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + bl_w + (bl_w - s_w)/2, dim_y + 2, "350", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + w_px - s_w/2, dim_y + 2, "300", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        
        dim_x = x0 - 6
        d.add(Line(dim_x, y0, dim_x, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0, dim_x + 2, y0, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + bot_h, dim_x + 2, y0 + bot_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + h_px, dim_x + 2, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(dim_x - 2, y0 + bot_h/2 - 2, "1400", fontName="Helvetica", fontSize=6, textAnchor="end", fillColor=dimension_color))
        d.add(String(dim_x - 2, y0 + bot_h + top_h/2 - 2, "2000", fontName="Helvetica", fontSize=6, textAnchor="end", fillColor=dimension_color))

    elif 'D1' in ref or 'D1' in desc:
        door_w = 950 * scale
        win_w = 625 * scale
        brick_h = 750 * scale
        win_h = 1350 * scale
        
        d.add(Rect(x0, y0, door_w, h_px, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + door_w/2, y0 + h_px/2 - 3, "LDIn G1", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0, y0 + h_px, x0 + door_w, y0 + h_px/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0, y0, x0 + door_w, y0 + h_px/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        brick_color = colors.HexColor('#C0392B')
        d.add(Rect(x0 + door_w, y0, win_w * 2, brick_h, fillColor=brick_color, strokeColor=frame_color, strokeWidth=1))
        by = y0 + 2
        while by < y0 + brick_h:
            d.add(Line(x0 + door_w, by, x0 + w_px, by, strokeColor=colors.HexColor('#FFFFFF'), strokeWidth=0.5))
            by += 4
        
        d.add(Rect(x0 + door_w, y0 + brick_h, win_w, win_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + door_w + win_w/2, y0 + brick_h + win_h/2 - 3, "G2", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0 + door_w, y0 + h_px, x0 + door_w + win_w, y0 + brick_h + win_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0 + door_w, y0 + brick_h, x0 + door_w + win_w, y0 + brick_h + win_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        d.add(Rect(x0 + door_w + win_w, y0 + brick_h, win_w, win_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + door_w + win_w + win_w/2, y0 + brick_h + win_h/2 - 3, "G2", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        d.add(Line(x0 + door_w + win_w, y0 + h_px, x0 + w_px, y0 + brick_h + win_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(Line(x0 + door_w + win_w, y0 + brick_h, x0 + w_px, y0 + brick_h + win_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        
        dim_y = y0 + h_px + 6
        d.add(Line(x0, dim_y, x0 + w_px, dim_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0, dim_y - 2, x0, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + door_w, dim_y - 2, x0 + door_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + door_w + win_w, dim_y - 2, x0 + door_w + win_w, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px, dim_y - 2, x0 + w_px, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(x0 + door_w/2, dim_y + 2, "950", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + door_w + win_w/2, dim_y + 2, "625", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        d.add(String(x0 + door_w + win_w + win_w/2, dim_y + 2, "625", fontName="Helvetica", fontSize=5.5, textAnchor="middle", fillColor=dimension_color))
        
        dim_x = x0 - 6
        d.add(Line(dim_x, y0, dim_x, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0, dim_x + 2, y0, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + brick_h, dim_x + 2, y0 + brick_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + h_px, dim_x + 2, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(dim_x - 2, y0 + brick_h/2 - 2, "750", fontName="Helvetica", fontSize=5.5, textAnchor="end", fillColor=dimension_color))
        d.add(String(dim_x - 2, y0 + brick_h + win_h/2 - 2, "1350", fontName="Helvetica", fontSize=5.5, textAnchor="end", fillColor=dimension_color))

    elif 'W4' in ref or 'W4' in desc:
        top_h = 500 * scale
        bot_h = 700 * scale
        
        d.add(Rect(x0, y0 + bot_h, w_px, top_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + w_px/2, y0 + bot_h + top_h/2 - 3, "FIXED G2", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        ly = y0 + bot_h + 3 * scale
        while ly < y0 + bot_h + top_h - 2:
            d.add(Line(x0, ly, x0 + w_px, ly, strokeColor=colors.HexColor('#7F7F7F'), strokeWidth=0.5))
            ly += 8 * scale
            
        d.add(Rect(x0, y0, w_px, bot_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
        d.add(String(x0 + w_px/2, y0 + bot_h/2 - 8, "FIXED G1", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
        cx = x0 + w_px / 2
        cy = y0 + bot_h / 2 + 5 * scale
        d.add(Circle(cx, cy, 10 * scale, fillColor=colors.white, strokeColor=frame_color, strokeWidth=0.8))
        d.add(Line(cx - 7 * scale, cy, cx + 7 * scale, cy, strokeColor=frame_color, strokeWidth=0.6))
        d.add(Line(cx, cy - 7 * scale, cx, cy + 7 * scale, strokeColor=frame_color, strokeWidth=0.6))
        
        dim_y = y0 + h_px + 6
        d.add(Line(x0, dim_y, x0 + w_px, dim_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0, dim_y - 2, x0, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px, dim_y - 2, x0 + w_px, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(x0 + w_px/2, dim_y + 2, "900", fontName="Helvetica", fontSize=6.5, textAnchor="middle", fillColor=dimension_color))
        
        dim_x = x0 - 6
        d.add(Line(dim_x, y0, dim_x, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0, dim_x + 2, y0, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + bot_h, dim_x + 2, y0 + bot_h, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + h_px, dim_x + 2, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(dim_x - 2, y0 + bot_h/2 - 2, "700", fontName="Helvetica", fontSize=6.5, textAnchor="end", fillColor=dimension_color))
        d.add(String(dim_x - 2, y0 + bot_h + top_h/2 - 2, "500", fontName="Helvetica", fontSize=6.5, textAnchor="end", fillColor=dimension_color))

    else:
        has_transom = (H >= 1400)
        n_panels = item.n_panels or 1
        
        if has_transom:
            top_h = 400 * scale
            bot_h = (H - 400) * scale
            
            d.add(Rect(x0, y0 + bot_h, w_px, top_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
            d.add(String(x0 + w_px/2, y0 + bot_h + top_h/2 - 3, "FIXED", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
            
            pane_w = w_px / n_panels
            for p in range(n_panels):
                px = x0 + p * pane_w
                d.add(Rect(px, y0, pane_w, bot_h, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
                label = "FIXED" if sys_cat == 'fixed' else f"Pane {p+1}"
                d.add(String(px + pane_w/2, y0 + bot_h/2 - 3, label, fontName="Helvetica-Bold", fontSize=7, textAnchor="middle", fillColor=text_color))
                
                if sys_cat == 'casement':
                    if p % 2 == 0:
                        d.add(Line(px, y0 + bot_h, px + pane_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
                        d.add(Line(px, y0, px + pane_w, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
                    else:
                        d.add(Line(px + pane_w, y0 + bot_h, px, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
                        d.add(Line(px + pane_w, y0, px, y0 + bot_h/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
        else:
            pane_w = w_px / n_panels
            for p in range(n_panels):
                px = x0 + p * pane_w
                d.add(Rect(px, y0, pane_w, h_px, fillColor=glass_color, strokeColor=frame_color, strokeWidth=1))
                label = "FIXED" if sys_cat == 'fixed' else f"Pane {p+1}"
                d.add(String(px + pane_w/2, y0 + h_px/2 - 3, label, fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=text_color))
                
                if sys_cat == 'casement':
                    if p % 2 == 0:
                        d.add(Line(px, y0 + h_px, px + pane_w, y0 + h_px/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
                        d.add(Line(px, y0, px + pane_w, y0 + h_px/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
                    else:
                        d.add(Line(px + pane_w, y0 + h_px, px, y0 + h_px/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))
                        d.add(Line(px + pane_w, y0, px, y0 + h_px/2, strokeColor=text_color, strokeWidth=0.5, strokeDashArray=[2, 2]))

        # Dimensions
        dim_y = y0 + h_px + 6
        d.add(Line(x0, dim_y, x0 + w_px, dim_y, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0, dim_y - 2, x0, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(x0 + w_px, dim_y - 2, x0 + w_px, dim_y + 2, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(x0 + w_px/2, dim_y + 2, str(W), fontName="Helvetica", fontSize=6.5, textAnchor="middle", fillColor=dimension_color))
        
        dim_x = x0 - 6
        d.add(Line(dim_x, y0, dim_x, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0, dim_x + 2, y0, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(Line(dim_x - 2, y0 + h_px, dim_x + 2, y0 + h_px, strokeColor=dimension_color, strokeWidth=0.8))
        d.add(String(dim_x - 2, y0 + h_px/2 - 2, str(H), fontName="Helvetica", fontSize=6.5, textAnchor="end", fillColor=dimension_color))

    d.add(String(dw/2, 4, "Viewed from Inside", fontName="Helvetica", fontSize=7, textAnchor="middle", fillColor=blue_text))
    return d


def _styles():
    ss = getSampleStyleSheet()
    return {
        'h1': ParagraphStyle('h1', fontSize=20, fontName='Helvetica-Bold',
                              textColor=TEXT_DARK, leading=24, spaceAfter=6),
        'h2': ParagraphStyle('h2', fontSize=12, fontName='Helvetica-Bold',
                              textColor=TEXT_DARK, leading=15, spaceAfter=4),
        'h3': ParagraphStyle('h3', fontSize=10, fontName='Helvetica-Bold',
                              textColor=TEXT_DARK, leading=12, spaceAfter=3),
        'body': ParagraphStyle('body', fontSize=9, fontName='Helvetica',
                               textColor=TEXT_DARK, leading=12, spaceAfter=2),
        'body_center': ParagraphStyle('body_center', fontSize=9, fontName='Helvetica',
                                      alignment=TA_CENTER, textColor=TEXT_DARK, leading=12),
        'body_bold_center': ParagraphStyle('body_bold_center', fontSize=9, fontName='Helvetica-Bold',
                                           alignment=TA_CENTER, textColor=TEXT_DARK, leading=12),
        'yellow_header': ParagraphStyle('yellow_header', fontSize=9, fontName='Helvetica-Bold',
                                        alignment=TA_CENTER, textColor=TEXT_DARK),
        'small': ParagraphStyle('small', fontSize=7.5, fontName='Helvetica',
                                textColor=TEXT_DARK, leading=10),
        'center': ParagraphStyle('center', fontSize=9, fontName='Helvetica',
                                  alignment=TA_CENTER, textColor=TEXT_DARK),
        'right': ParagraphStyle('right', fontSize=9, fontName='Helvetica',
                                 alignment=TA_RIGHT, textColor=TEXT_DARK),
        'bold_right': ParagraphStyle('bold_right', fontSize=9, fontName='Helvetica-Bold',
                                      alignment=TA_RIGHT),
        'white': ParagraphStyle('white', fontSize=9, fontName='Helvetica-Bold',
                                 textColor=WHITE),
        'detail': ParagraphStyle('detail', fontSize=8, fontName='Helvetica',
                                 textColor=TEXT_DARK, leading=11),
        'detail_bold': ParagraphStyle('detail_bold', fontSize=8, fontName='Helvetica-Bold',
                                      textColor=TEXT_DARK, leading=11),
        'company_header': ParagraphStyle('company_header', fontSize=12, fontName='Helvetica-Bold',
                                         textColor=TEXT_DARK, leading=14, spaceAfter=2),
        'company_subtext': ParagraphStyle('company_subtext', fontSize=8, fontName='Helvetica',
                                          textColor=TEXT_DARK, leading=11),
    }


def _tbl_style(header_color=DARK_BLUE):
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR',     (0, 0), (-1, 0), WHITE),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 8),
        ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.3, GREY_LINE),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ])


def _header_block(elems, company, customer, address, quote_no, cust_ref,
                  quote_date, salesman_name, salesman_phone, salesman_email, report_title='Quotation'):
    S = _styles()
    
    # ── Company Header with Title ──
    company_text = (
        f"<b>{company.company_name}</b><br/>"
        f"{company.address_line1}"
        f"{', ' + company.address_line2 if company.address_line2 else ''}<br/>"
        f"{company.city}{', ' + company.state if company.state else ''} – {company.pincode}<br/>"
        f"Tel: {company.phone} | Email: {company.email}"
    )
    elems.append(Paragraph(company_text, S['company_subtext']))
    elems.append(Spacer(1, 3 * mm))
    elems.append(Paragraph(f"<b>{report_title}</b>", S['h1']))
    elems.append(Spacer(1, 2 * mm))

    # ── To / Deliver To Section ──
    to_lines = [f"<b>{customer.name}</b>", address.replace('\n', '<br/>')]
    if customer.phone:
        to_lines.append(customer.phone)
    if customer.email:
        to_lines.append(customer.email)
    to_text = '<br/>'.join(to_lines)

    deliver_to = customer.delivery_address if customer.delivery_address else address
    deliver_to_text = deliver_to.replace('\n', '<br/>')

    addr_data = [
        ['To', 'Deliver to'],
        [Paragraph(to_text, S['body']), Paragraph(deliver_to_text, S['body'])]
    ]
    t2 = Table(addr_data, colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    t2.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), HEADER_GREY),
        ('TEXTCOLOR',   (0, 0), (-1, 0), WHITE),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 9),
        ('GRID',        (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
    ]))
    elems.append(t2)
    elems.append(Spacer(1, 3 * mm))

    # ── Quote Meta Information ──
    salesperson_cell = []
    if salesman_phone:
        salesperson_cell.append(salesman_phone)
    if salesman_email:
        salesperson_cell.append(salesman_email)
    salesperson_cell_text = '<br/>'.join(salesperson_cell)

    meta = [
        ['Quote No.', 'Customer Ref.', 'Quote Date', f'Sales Person - {salesman_name}'],
        [quote_no, cust_ref, quote_date, Paragraph(salesperson_cell_text, S['body'])]
    ]
    tm = Table(meta, colWidths=[35 * mm, 35 * mm, 35 * mm, CONTENT_W - 105 * mm])
    tm.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), HEADER_GREY),
        ('TEXTCOLOR',   (0, 0), (-1, 0), WHITE),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 8.5),
        ('FONTSIZE',    (0, 1), (-1, 1), 8),
        ('GRID',        (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elems.append(tm)
    elems.append(Spacer(1, 4 * mm))
    return tm


def generate_quotation_pdf(quote) -> bytes:
    from catalog.models import CompanySettings
    company = CompanySettings.get()
    S = _styles()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=LMARGIN, rightMargin=RMARGIN,
                          topMargin=TMARGIN, bottomMargin=BMARGIN)
    
    frame_first = Frame(LMARGIN, BMARGIN, CONTENT_W, PAGE_H - TMARGIN - BMARGIN, id='first')
    header_space = 25 * mm
    frame_later = Frame(LMARGIN, BMARGIN, CONTENT_W, PAGE_H - TMARGIN - BMARGIN - header_space, id='later')
    
    def draw_later_page_header(canvas, doc):
        canvas.saveState()
        if hasattr(doc, 'quote_meta_table'):
            doc.quote_meta_table.wrapOn(canvas, CONTENT_W, 20 * mm)
            doc.quote_meta_table.drawOn(canvas, LMARGIN, PAGE_H - TMARGIN - doc.quote_meta_table._height)
        canvas.restoreState()
        
    temp_first = PageTemplate(id='FirstPage', frames=frame_first)
    temp_later = PageTemplate(id='LaterPage', frames=frame_later, onPage=draw_later_page_header)
    doc.addPageTemplates([temp_first, temp_later])
    
    elems = [NextPageTemplate('LaterPage')]

    customer = quote.project.customer
    address = customer.full_address
    salesman_name = quote.salesman.get_full_name() if quote.salesman else ''
    salesman_phone = ''
    salesman_email = ''
    if quote.salesman:
        salesman_email = quote.salesman.email
        try:
            salesman_phone = quote.salesman.profile.phone
        except Exception:
            salesman_phone = ''
            
    quote_date = quote.quote_date.strftime('%d-%m-%Y')
    cust_ref = quote.project.reference

    meta_table = _header_block(elems, company, customer, address,
                               quote.quote_no, cust_ref, quote_date,
                               salesman_name, salesman_phone, salesman_email)
    doc.quote_meta_table = meta_table

    # ── Salutation ──
    salutation_name = customer.name.split()[0] if customer.name else 'Customer'
    elems.append(Paragraph(f"Dear {salutation_name},", S['body']))
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(
        "Thank you for giving my company the opportunity to provide you with the following quotation for your perusal.", S['body']))
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(
        "Should you require any further information, please feel free to contact me at the above number.", S['body']))
    elems.append(Spacer(1, 5 * mm))

    # ── Sales Lines Table ──
    items = quote.items.select_related('system', 'glass', 'color').all()
    sales_table_data = [
        [
            Paragraph("<b>Sales Line</b>", S['white']),
            Paragraph("<b>Details</b>", S['white']),
            Paragraph("<b>Qty</b>", S['white']),
            Paragraph("<b>Rate (₹)</b>", S['white']),
            Paragraph("<b>Amount (₹)</b>", S['white'])
        ]
    ]

    for item in items:
        drawing = draw_window_diagram(item)
        line_ref_text = f"<b>{item.line_no}</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b>{item.reference}</b>"
        col1_content = [Paragraph(line_ref_text, S['body_bold_center']), Spacer(1, 2 * mm), drawing]

        glass_str = str(item.glass) if item.glass else 'N/A'
        color_str = str(item.color) if item.color else 'Standard'
        
        detail_lines = [
            f"<b>{item.location}</b>",
            "",
            f"{item.system.name}",
            f"{item.description or 'Standard Window'}",
            f"{item.width}w x {item.height}h ({item.area_sqft:.2f} sqft)",
            f"{glass_str}",
            f"Weight: {item.weight_kg:.2f} kg",
            f"Colour: {color_str}",
        ]
        
        # Add hardware breakdown
        hw_list = item.get_hardware_components()
        if hw_list:
            detail_lines.append("<br/><b>Hardware Components:</b>")
            for hw in hw_list:
                detail_lines.append(f"• {hw['name']}: {hw['qty']} {hw['unit']} @ ₹{hw['unit_cost']:,.2f} = ₹{hw['total_cost']:,.2f}")
                
        detail_text = '<br/>'.join(detail_lines)
        col2_content = Paragraph(detail_text, S['detail'])

        col3_content = Paragraph(f"<b>{item.qty}</b>", S['body_center'])
        col4_content = Paragraph(f"{item.unit_rate:,.2f}", S['right'])
        col5_content = Paragraph(f"<b>{item.total_amount:,.2f}</b>", S['bold_right'])

        sales_table_data.append([col1_content, col2_content, col3_content, col4_content, col5_content])

    st = Table(sales_table_data, colWidths=[48 * mm, 78 * mm, 10 * mm, 22 * mm, 22 * mm])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_GREY),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elems.append(st)
    elems.append(Spacer(1, 4 * mm))

    # ── Master Totals Block ──
    left_summary_data = [
        ['Total Area*', f"{quote.total_area_sqft:.2f} sqft"],
        ['Total Units', f"{items.count()}"],
        ['Total Weight', f"{quote.total_weight_kg:.2f} kg"],
    ]
    left_table = Table(left_summary_data, colWidths=[30 * mm, 45 * mm])
    left_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    left_flowables = [left_table, Spacer(1, 3 * mm)]
    if quote.payment_terms:
        left_flowables.append(Paragraph("<b>Payment Terms</b>", S['h3']))
        left_flowables.append(Paragraph(quote.payment_terms.replace('\n', '<br/>'), S['body']))

    right_charges_data = []
    right_charges_data.append(['Total', f"₹ {quote.subtotal:,.2f}"])
    
    if float(quote.discount_value) > 0:
        right_charges_data.append([f'Discount ({quote.discount_value}%)', f'– ₹ {quote.discount_amount:,.2f}'])
    if float(quote.installation_value) > 0:
        label = (f'Installation ({quote.installation_value}%)'
                 if quote.installation_type == 'percent'
                 else f'Installation (₹{quote.installation_value}/sqft)')
        right_charges_data.append([label, f"₹ {quote.installation_amount:,.2f}"])
    if float(quote.freight) > 0:
        right_charges_data.append(['Freight', f"₹ {float(quote.freight):,.2f}"])
    if float(quote.lifting_charges) > 0:
        right_charges_data.append(['Lifting Charges', f"₹ {float(quote.lifting_charges):,.2f}"])

    right_charges_data.append(['<b>Total Taxable</b>', f"<b>₹ {quote.taxable_amount:,.2f}</b>"])
    
    if quote.apply_sgst:
        right_charges_data.append([f'SGST ({quote.sgst_rate}%)', f"₹ {quote.sgst_amount:,.2f}"])
    if quote.apply_cgst:
        right_charges_data.append([f'CGST ({quote.cgst_rate}%)', f"₹ {quote.cgst_amount:,.2f}"])
    if quote.apply_igst:
        right_charges_data.append([f'IGST ({quote.igst_rate}%)', f"₹ {quote.igst_amount:,.2f}"])
    
    right_charges_data.append(['Grand Total', f"₹ {quote.grand_total:,.2f}"])

    formatted_charges = []
    for r_idx, row in enumerate(right_charges_data):
        label_style = S['body']
        val_style = S['right']
        if r_idx == len(right_charges_data) - 1:
            label_style = ParagraphStyle('gt_lbl', parent=S['bold_right'], fontSize=9.5)
            val_style = ParagraphStyle('gt_val', parent=S['bold_right'], fontSize=9.5)
        elif '<b>' in row[0] or '<b>' in row[1]:
            label_style = S['bold_right']
            val_style = S['bold_right']
            
        formatted_charges.append([
            Paragraph(row[0], label_style),
            Paragraph(row[1], val_style)
        ])

    right_table = Table(formatted_charges, colWidths=[55 * mm, 35 * mm])
    rt_style = [
        ('GRID', (0, 0), (-1, -1), 0.3, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BACKGROUND', (0, len(right_charges_data) - 1), (-1, len(right_charges_data) - 1), YELLOW_HIGHLIGHT),
    ]
    right_table.setStyle(TableStyle(rt_style))

    master_table = Table([[left_flowables, right_table]], colWidths=[85 * mm, 95 * mm])
    master_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elems.append(master_table)
    elems.append(Spacer(1, 4 * mm))
    
    elems.append(Paragraph(
        '*The area calculation will be accurate only for simple rectangular frames', S['small']))
    elems.append(Spacer(1, 3 * mm))
    
    elems.append(Paragraph("We trust that this quotation meets with your requirements.", S['body']))
    elems.append(Spacer(1, 2 * mm))
    
    validity_days = company.quotation_validity_days or 30
    elems.append(Paragraph(
        f"Please note that this quote is valid for a period of {validity_days} days from the above date.", S['body']))
    elems.append(Spacer(1, 6 * mm))
    
    # Signature Block
    sig_text = (
        f"Thanking you,<br/>"
        f"Yours sincerely,<br/><br/>"
        f"<b>{salesman_name}</b><br/>"
        f"Sales Representative<br/>"
        f"{company.company_name}"
    )
    elems.append(Paragraph(sig_text, S['body']))

    if company.quotation_terms:
        elems.append(Spacer(1, 4 * mm))
        elems.append(Paragraph('Terms & Conditions', S['h3']))
        elems.append(Paragraph(company.quotation_terms.replace('\n', '<br/>'), S['small']))

    doc.build(elems)
    return buf.getvalue()


def generate_production_document_pdf(production_job) -> bytes:
    """Production document per item – shows cuts, hardware, assembly"""
    from catalog.models import CompanySettings
    company = CompanySettings.get()
    S = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=TMARGIN, bottomMargin=BMARGIN,
                             leftMargin=LMARGIN, rightMargin=RMARGIN)
    elems = []

    project = production_job.project
    customer = project.customer
    job_date = production_job.created_at.strftime('%d-%m-%Y')

    # ── Header ──
    elems.append(Paragraph(f"<b>{company.company_name}</b>", S['h2']))
    elems.append(Paragraph(
        f"{company.address_line1}, {company.city}", S['small']))
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph('<b>Production Document</b>', S['h1']))
    elems.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=DARK_BLUE))
    elems.append(Spacer(1, 3 * mm))

    meta = [
        [production_job.job_no, f"1/{production_job.job_no}", '',
         f"Qty {production_job.items.count()}"],
        [customer.name, project.reference, '', ''],
    ]
    mt = Table(meta, colWidths=[50 * mm, 50 * mm, CONTENT_W - 130 * mm, 30 * mm])
    mt.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.3, GREY_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elems.append(mt)
    elems.append(Spacer(1, 4 * mm))

    # Per item production detail
    for job_item in production_job.items.select_related(
            'measurement__system', 'measurement__glass', 'measurement__color').all():
        m = job_item.measurement
        if m is None:
            # Production item was created without a linked measurement (rare
            # but possible if the measurement was deleted after job generation).
            header_text = f"<b>{job_item.line_no} / {job_item.reference} – {job_item.location}</b>"
        else:
            header_text = f"<b>{m.line_no} / {m.reference} – {m.location}</b>"
        elems.append(KeepTogether([
            Paragraph(header_text, S['h3']),
            _item_production_table(job_item, S),
            Spacer(1, 5 * mm),
        ]))

    doc.build(elems)
    return buf.getvalue()


def _item_production_table(job_item, S):
    m = job_item.measurement
    if m is None:
        # Fallback to ProductionItem fields if measurement was deleted
        info = [
            ['System', job_item.system.name if job_item.system else ''],
            ['Description', job_item.description or ''],
            ['Size', f"{job_item.width}w × {job_item.height}h mm"],
            ['Glazing', str(job_item.glass) if job_item.glass else 'N/A'],
        ]
    else:
        info = [
            ['System', m.system.name if m.system else ''],
            ['Description', m.description or ''],
            ['Size', f"{m.effective_width}w × {m.effective_height}h mm"],
            ['Glazing', str(m.glass) if m.glass else 'N/A'],
        ]
    it = Table(info, colWidths=[35 * mm, CONTENT_W - 35 * mm])
    it.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E0')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#EDF2F7'), WHITE]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return it


def generate_cutting_list_pdf(optimization_run) -> bytes:
    """Optimized cutting list PDF – matches Windowmaker Cutting List format"""
    from catalog.models import CompanySettings
    from production.models import OptimizationRun
    company = CompanySettings.get()
    S = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=TMARGIN, bottomMargin=BMARGIN,
                             leftMargin=LMARGIN, rightMargin=RMARGIN)
    elems = []

    project = optimization_run.production_job.project
    run_date = optimization_run.created_at.strftime('%d-%m-%Y')

    # Header
    hdr = Table([
        [Paragraph(f"<b>{company.company_name}</b>", S['h2']),
         Paragraph('<b>Cutting List</b>', S['h1']),
         Paragraph(run_date, S['body'])]
    ], colWidths=[60 * mm, 80 * mm, CONTENT_W - 140 * mm])
    hdr.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elems.append(hdr)
    elems.append(Paragraph(
        f"Batch 1 / {optimization_run.production_job.job_no}  &nbsp;&nbsp; "
        f"Saw station: Prof. Saw &nbsp;&nbsp; "
        f"Customer: {project.customer.name} &nbsp;&nbsp; Cust. Ref.: {project.reference}",
        S['small']))
    elems.append(HRFlowable(width=CONTENT_W, thickness=1, color=DARK_BLUE))
    elems.append(Spacer(1, 3 * mm))

    # Per-profile sections
    for segment in optimization_run.segments.select_related('profile').order_by('profile__category'):
        elems.append(Paragraph(f"<b>{segment.profile.name}</b>  {segment.profile.stock_no}", S['h3']))

        # Group by bar
        bars = {}
        for cut in segment.cuts.select_related('production_item__measurement').order_by('bar_number'):
            bars.setdefault(cut.bar_number, [])
            bars[cut.bar_number].append(cut)

        for bar_no, cuts in bars.items():
            # Use the actual stock length of this specific bar (stored on each
            # OptimizedCut record) rather than the segment-level modal length,
            # which is wrong whenever a profile was cut from multiple stock sizes.
            bar_len = cuts[0].bar_length_mm if cuts else segment.bar_length_mm
            bar_label = f"{1} x {bar_len}"
            elems.append(Paragraph(f"Bar {bar_no}  –  {bar_label}", S['small']))

            cut_data = [[
                'Profile', 'Line', 'Ref', 'Qty', 'Length', 'Dims', 'Angle', 'Position'
            ]]
            for c in cuts:
                item = c.production_item
                m = item.measurement if item else None
                ref = f"{optimization_run.production_job.job_no}/{m.line_no}" if m else ''
                line = item.line_no if item else ''
                dims = f"{item.width}×{item.height}" if item else ''
                angle_str = ''
                if c.left_angle != 90 or c.right_angle != 90:
                    angle_str = f"{c.left_angle:.1f}° / {c.right_angle:.1f}°"
                else:
                    angle_str = '\\ /'
                cut_data.append([
                    segment.profile.stock_no,
                    str(line),
                    ref,
                    '1',
                    str(c.cut_length_mm),
                    dims,
                    angle_str,
                    _translate_position_code(c.position_code or ''),
                ])
            total_cut = sum(c.cut_length_mm for c in cuts)
            kerf_loss = max(0, (len(cuts) - 1) * optimization_run.kerf_mm)
            reserved_end_waste = optimization_run.end_waste_mm if cuts else 0
            remaining = bar_len - total_cut - kerf_loss - reserved_end_waste
            offcut = remaining if remaining >= optimization_run.min_reusable_mm else 0
            scrap = remaining if 0 < remaining < optimization_run.min_reusable_mm else 0
            utilisation = round((total_cut + kerf_loss) / bar_len * 100, 2) if bar_len else 0

            if kerf_loss > 0:
                cut_data.append(['', '', '', '', '', '', 'Kerf', str(kerf_loss)])
            if offcut > 0:
                cut_data.append(['', '', '', '', '', '', 'Offcut', str(offcut)])
            if scrap > 0:
                cut_data.append(['', '', '', '', '', '', 'Scrap', str(scrap)])
            cut_data.append(['', '', '', '', '', '', 'Util', f'{utilisation:.2f}%'])

            ct = Table(cut_data, colWidths=[30 * mm, 12 * mm, 22 * mm, 10 * mm,
                                             16 * mm, 18 * mm, 20 * mm, CONTENT_W - 128 * mm],
                       repeatRows=1)
            ts = _tbl_style(MID_BLUE)
            ct.setStyle(ts)
            elems.append(ct)
            elems.append(Spacer(1, 2 * mm))

        elems.append(Paragraph(
            f"Total: {segment.total_pieces} pcs  {segment.total_cut_length_mm} mm  "
            f"({segment.bars_required} bars)", S['small']))
        elems.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=GREY_LINE))
        elems.append(Spacer(1, 3 * mm))

    doc.build(elems)
    return buf.getvalue()


def generate_load_list_pdf(optimization_run) -> bytes:
    """
    Load List PDF -- per-profile summary of how many stock bars (grouped by
    length) are needed for a job, without the full cut-by-cut breakdown that
    the Cutting List shows. Matches the Windowmaker "Load List (Optimised)"
    report format: Description / Stock No / Qty / Size / Bars, where 'Bars'
    reads e.g. "6 x 5750" or, if a segment used more than one stock length,
    multiple lines like "1 x 3496" followed by "6 x 5750".
    """
    from catalog.models import CompanySettings
    company = CompanySettings.get()
    S = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=TMARGIN, bottomMargin=BMARGIN,
                             leftMargin=LMARGIN, rightMargin=RMARGIN)
    elems = []

    job = optimization_run.production_job
    project = job.project
    customer = project.customer
    run_date = optimization_run.created_at.strftime('%d-%m-%Y')

    # Header -- same layout convention as generate_cutting_list_pdf above
    hdr = Table([
        [Paragraph(f"<b>{company.company_name}</b>", S['h2']),
         Paragraph('<b>Load List</b>', S['h1']),
         Paragraph(run_date, S['body'])]
    ], colWidths=[60 * mm, 80 * mm, CONTENT_W - 140 * mm])
    hdr.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elems.append(hdr)
    elems.append(Paragraph(
        f"Batch 1 / {job.job_no}  &nbsp;&nbsp; "
        f"Saw station: Prof. Saw &nbsp;&nbsp; "
        f"Customer: {customer.name} &nbsp;&nbsp; Cust. Ref.: {project.reference}",
        S['small']))
    elems.append(HRFlowable(width=CONTENT_W, thickness=1, color=DARK_BLUE))
    elems.append(Spacer(1, 3 * mm))

    table_data = [['Description', 'Stock No.', 'Qty', 'Size', 'Bars']]

    for segment in optimization_run.segments.select_related('profile').order_by('profile__category'):
        if not segment.bars_required:
            continue
        # In this schema a segment uses one stock length for all its bars
        # (segment.bar_length_mm), matching how generate_cutting_list_pdf
        # above reads it -- so there's a single "qty x length" line per
        # profile, e.g. "6 x 5750", rather than a per-bar length breakdown.
        table_data.append([
            segment.profile.name, segment.profile.stock_no, '', '',
            f"{segment.bars_required} x {segment.bar_length_mm}",
        ])
        table_data.append([
            'Total', '', str(segment.total_pieces),
            str(segment.total_cut_length_mm), str(segment.bars_required),
        ])

    col_w = [55 * mm, 30 * mm, 18 * mm, 25 * mm, CONTENT_W - 128 * mm]
    lt = Table(table_data, colWidths=col_w, repeatRows=1)
    ts = _tbl_style(MID_BLUE)
    # Bold the 'Total' rows so they stand out, same convention as Windowmaker
    for i, row in enumerate(table_data[1:], start=1):
        if row[0] == 'Total':
            ts.add('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold')
            ts.add('LINEABOVE', (0, i), (-1, i), 0.5, GREY_LINE)
    lt.setStyle(ts)
    elems.append(lt)

    doc.build(elems)
    return buf.getvalue()