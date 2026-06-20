"""
CutFlow – PDF Report Engine
Generates industry-grade quotation and production PDFs using ReportLab.
Layout inspired by Windowmaker Software reports.
"""
import io
from datetime import date
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, PageBreak, KeepTogether
)

# ── Colour Palette ────────────────────────────────────────────────────────────
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


def _styles():
    ss = getSampleStyleSheet()
    return {
        'h1': ParagraphStyle('h1', fontSize=18, fontName='Helvetica-Bold',
                              textColor=DARK_BLUE, leading=22),
        'h2': ParagraphStyle('h2', fontSize=11, fontName='Helvetica-Bold',
                              textColor=MID_BLUE, leading=14),
        'h3': ParagraphStyle('h3', fontSize=9, fontName='Helvetica-Bold',
                              textColor=DARK_BLUE, leading=12),
        'body': ParagraphStyle('body', fontSize=8.5, fontName='Helvetica',
                               textColor=GREY_TXT, leading=12),
        'small': ParagraphStyle('small', fontSize=7.5, fontName='Helvetica',
                                textColor=GREY_TXT, leading=10),
        'center': ParagraphStyle('center', fontSize=9, fontName='Helvetica',
                                  alignment=TA_CENTER, textColor=GREY_TXT),
        'right': ParagraphStyle('right', fontSize=9, fontName='Helvetica',
                                 alignment=TA_RIGHT, textColor=GREY_TXT),
        'bold_right': ParagraphStyle('bold_right', fontSize=9, fontName='Helvetica-Bold',
                                      alignment=TA_RIGHT),
        'white': ParagraphStyle('white', fontSize=9, fontName='Helvetica-Bold',
                                 textColor=WHITE),
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


def _header_block(elems, company, customer_name, address, quote_no, cust_ref,
                  quote_date, salesman_name, report_title='Quotation'):
    S = _styles()
    # Company + title row
    company_text = (
        f"<b>{company.company_name}</b><br/>"
        f"{company.address_line1}"
        f"{', ' + company.address_line2 if company.address_line2 else ''}<br/>"
        f"{company.city}{', ' + company.state if company.state else ''} – {company.pincode}<br/>"
        f"Tel: {company.phone} | {company.email}"
    )
    header_data = [
        [Paragraph(company_text, S['body']),
         Paragraph(f"<b>{report_title}</b>", S['h1'])]
    ]
    t = Table(header_data, colWidths=[85 * mm, CONTENT_W - 85 * mm])
    t.setStyle(TableStyle([
        ('VALIGN',  (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',   (1, 0), (1, 0), 'RIGHT'),
    ]))
    elems.append(t)
    elems.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=DARK_BLUE))
    elems.append(Spacer(1, 3 * mm))

    # To / Deliver To row
    to_text = f"<b>{customer_name}</b><br/>{address.replace(chr(10), '<br/>')}"
    addr_data = [['To', 'Deliver to'],
                 [Paragraph(to_text, S['body']), Paragraph(to_text, S['body'])]]
    t2 = Table(addr_data, colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    t2.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0), WHITE),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 8),
        ('GRID',        (0, 0), (-1, -1), 0.3, GREY_LINE),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
    ]))
    elems.append(t2)
    elems.append(Spacer(1, 2 * mm))

    # Quote meta row
    meta = [['Quote No.', 'Customer Ref.', 'Quote Date', f'Sales Person – {salesman_name}'],
            [quote_no, cust_ref, quote_date, '']]
    tm = Table(meta, colWidths=[35 * mm, 40 * mm, 35 * mm, CONTENT_W - 110 * mm])
    tm.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0), WHITE),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 8),
        ('FONTNAME',    (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 1), (-1, 1), 8),
        ('GRID',        (0, 0), (-1, -1), 0.3, GREY_LINE),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elems.append(tm)
    elems.append(Spacer(1, 4 * mm))


def generate_quotation_pdf(quote) -> bytes:
    from catalog.models import CompanySettings
    company = CompanySettings.get()
    S = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=TMARGIN, bottomMargin=BMARGIN,
                             leftMargin=LMARGIN, rightMargin=RMARGIN)
    elems = []

    customer = quote.project.customer
    address = customer.full_address
    salesman_name = quote.salesman.get_full_name() if quote.salesman else ''
    quote_date = quote.quote_date.strftime('%d-%m-%Y')
    cust_ref = quote.project.reference

    _header_block(elems, company, customer.name, address,
                  quote.quote_no, cust_ref, quote_date, salesman_name)

    # ── Salutation ──
    elems.append(Paragraph(f"Dear {customer.name.split()[0]},", S['body']))
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(
        "Thank you for giving us the opportunity to provide you with the following quotation "
        "for your perusal. Should you require any further information, please feel free to "
        "contact us.", S['body']))
    elems.append(Spacer(1, 4 * mm))

    # ── Sales Lines Table ──
    items = quote.items.select_related('system', 'glass', 'color').all()

    line_header = [['Sales Line', 'Details', 'Qty', 'Rate (₹)', 'Amount (₹)']]
    line_rows = []
    for item in items:
        glass_str = str(item.glass) if item.glass else 'N/A'
        color_str = str(item.color) if item.color else ''
        detail = (
            f"<b>{item.location}</b><br/>"
            f"{item.system.name}<br/>"
            f"{item.description or ''}<br/>"
            f"{item.width}w × {item.height}h ({item.area_sqft:.2f} sqft)<br/>"
            f"Glass: {glass_str}"
            f"{chr(10) + 'Colour: ' + color_str if color_str else ''}"
        )
        line_rows.append([
            f"<b>{item.line_no}</b>\n{item.reference}",
            Paragraph(detail, S['small']),
            str(item.qty),
            f"₹ {item.unit_rate:,.2f}",
            f"₹ {item.total_amount:,.2f}",
        ])

    tbl_data = line_header + line_rows
    col_w = [22 * mm, CONTENT_W - 22 - 16 - 28 - 28, 16 * mm, 28 * mm, 28 * mm]
    tl = Table(tbl_data, colWidths=col_w, repeatRows=1)
    ts = _tbl_style(MID_BLUE)
    ts.add('ALIGN', (2, 1), (-1, -1), 'RIGHT')
    tl.setStyle(ts)
    elems.append(tl)
    elems.append(Spacer(1, 4 * mm))

    # ── Totals Block ──
    totals_data = [
        ['Total Area*', f"{quote.total_area_sqft:.2f} sqft",
         'Total', f"₹ {quote.subtotal:,.2f}"],
        ['Total Units', str(items.count()), '', ''],
        ['Total Weight', f"{quote.total_weight_kg:.2f} kg", '', ''],
    ]

    charges = []
    if float(quote.discount_value) > 0:
        charges.append(['', '', f'Discount ({quote.discount_value}%)', f'₹ {quote.discount_amount:,.2f}'])
    if float(quote.installation_value) > 0:
        label = (f'Installation ({quote.installation_value}%)'
                 if quote.installation_type == 'percent'
                 else f'Installation (₹{quote.installation_value}/sqft)')
        charges.append(['', '', label, f'₹ {quote.installation_amount:,.2f}'])
    if float(quote.freight) > 0:
        charges.append(['', '', 'Freight', f'₹ {float(quote.freight):,.2f}'])
    if float(quote.lifting_charges) > 0:
        charges.append(['', '', 'Lifting Charges', f'₹ {float(quote.lifting_charges):,.2f}'])

    charges.append(['', '', '<b>Total Taxable</b>', f'<b>₹ {quote.taxable_amount:,.2f}</b>'])
    if quote.apply_sgst:
        charges.append(['', '', f'SGST ({quote.sgst_rate}%)', f'₹ {quote.sgst_amount:,.2f}'])
    if quote.apply_cgst:
        charges.append(['', '', f'CGST ({quote.cgst_rate}%)', f'₹ {quote.cgst_amount:,.2f}'])
    if quote.apply_igst:
        charges.append(['', '', f'IGST ({quote.igst_rate}%)', f'₹ {quote.igst_amount:,.2f}'])
    charges.append(['', '', '<b>Grand Total</b>', f'<b>₹ {quote.grand_total:,.2f}</b>'])

    all_rows = totals_data + charges
    # Convert strings to Paragraphs for bold markup
    for row in all_rows:
        for ci, cell in enumerate(row):
            if isinstance(cell, str) and ('<b>' in cell or '₹' in cell):
                row[ci] = Paragraph(cell, S['small'] if '₹' not in cell else S['body'])

    tot_tbl = Table(all_rows, colWidths=[35 * mm, 35 * mm, 60 * mm, CONTENT_W - 130 * mm])
    tot_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('GRID', (0, 0), (-1, -1), 0.3, GREY_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('BACKGROUND', (0, len(totals_data)), (1, -1), colors.white),
        ('BACKGROUND', (2, len(all_rows) - 1), (3, len(all_rows) - 1), GOLD),
        ('TEXTCOLOR', (2, len(all_rows) - 1), (3, len(all_rows) - 1), WHITE),
        ('FONTNAME', (2, len(all_rows) - 1), (3, len(all_rows) - 1), 'Helvetica-Bold'),
    ])
    tot_tbl.setStyle(tot_style)
    elems.append(tot_tbl)
    elems.append(Spacer(1, 3 * mm))
    elems.append(Paragraph(
        '*The area calculation will be accurate only for simple rectangular frames', S['small']))
    elems.append(Spacer(1, 5 * mm))

    # ── Terms ──
    if quote.payment_terms:
        elems.append(Paragraph('Payment Terms', S['h3']))
        elems.append(Paragraph(quote.payment_terms, S['body']))
        elems.append(Spacer(1, 3 * mm))

    if company.quotation_terms:
        elems.append(Paragraph('Terms & Conditions', S['h3']))
        elems.append(Paragraph(company.quotation_terms.replace('\n', '<br/>'), S['small']))
        elems.append(Spacer(1, 3 * mm))

    if quote.valid_until:
        elems.append(Paragraph(
            f"This quote is valid until {quote.valid_until.strftime('%d-%m-%Y')}.", S['body']))

    elems.append(Spacer(1, 8 * mm))
    elems.append(Paragraph(f"Thanking you,<br/>Yours sincerely,<br/><br/>"
                            f"<b>{salesman_name}</b><br/>"
                            f"{company.company_name}", S['body']))

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
        elems.append(KeepTogether([
            Paragraph(f"<b>{m.line_no} / {m.reference} – {m.location}</b>", S['h3']),
            _item_production_table(job_item, S),
            Spacer(1, 5 * mm),
        ]))

    doc.build(elems)
    return buf.getvalue()


def _item_production_table(job_item, S):
    m = job_item.measurement
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
            # Each cut now records the actual stock length it was placed on;
            # a segment can legitimately mix bar lengths (e.g. some cuts on
            # 3000mm offcuts, others on fresh 6000mm bars), so read it per
            # bar rather than assuming the whole segment is uniform.
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
