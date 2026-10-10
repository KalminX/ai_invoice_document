import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image, ImageDraw, ImageFont


def generate_pdf_invoice(
    output_path: str,
    supplier_name: str,
    invoice_number: str,
    date_str: str,
    due_date_str: str,
    bill_to: str,
    items: list,
    subtotal: str,
    tax: str,
    total: str,
    tax_id: str = "US-987654321",
    notes: str = "Payment due within 30 days. Thank you for your business."
):
    """Generates a professional PDF invoice using ReportLab."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
        fontName='Helvetica-Bold'
    )
    h2_style = ParagraphStyle(
        'VendorName',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e293b"),
        fontName='Helvetica-Bold'
    )
    body_style = ParagraphStyle(
        'InvoiceBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569")
    )
    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        fontName='Helvetica-Bold'
    )

    story = []

    # Header section: Supplier info & Invoice Title
    header_data = [
        [
            Paragraph(f"<b>{supplier_name}</b><br/>Tax ID: {tax_id}<br/>100 Enterprise Way, Suite 400<br/>San Francisco, CA 94105", body_style),
            Paragraph(f"INVOICE<br/><font size=11 color='#64748b'>#{invoice_number}</font>", title_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[320, 220])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=15))

    # Meta Section: Bill To & Invoice Dates
    meta_data = [
        [
            Paragraph(f"<b>Billed To:</b><br/>{bill_to}<br/>Finance Operations Team<br/>accounts-payable@company.com", body_style),
            Paragraph(f"<b>Invoice Date:</b> {date_str}<br/><b>Due Date:</b> {due_date_str}<br/><b>Currency:</b> USD", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[320, 220])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Line Items Table
    table_content = [
        [
            Paragraph("<b>#</b>", meta_val_style),
            Paragraph("<b>Description</b>", meta_val_style),
            Paragraph("<b>Qty</b>", meta_val_style),
            Paragraph("<b>Unit Price</b>", meta_val_style),
            Paragraph("<b>Amount</b>", meta_val_style)
        ]
    ]

    for idx, (desc, qty, unit_price, amt) in enumerate(items, 1):
        table_content.append([
            Paragraph(str(idx), body_style),
            Paragraph(desc, body_style),
            Paragraph(str(qty), body_style),
            Paragraph(f"${unit_price}", body_style),
            Paragraph(f"${amt}", meta_val_style)
        ])

    items_table = Table(table_content, colWidths=[25, 305, 50, 80, 80])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor("#cbd5e1")),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    # Totals Table
    totals_data = [
        ["", "", "Subtotal:", f"${subtotal}"],
        ["", "", "Tax (Estimated):", f"${tax}"],
        ["", "", "Total Amount Due:", f"${total}"]
    ]
    totals_table = Table(totals_data, colWidths=[200, 130, 130, 80])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (2, 2), (3, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (2, 2), (3, 2), 11),
        ('TEXTCOLOR', (2, 2), (3, 2), colors.HexColor("#0f172a")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (2, 2), (3, 2), 1, colors.HexColor("#0f172a")),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 25))

    # Notes
    story.append(Paragraph(f"<b>Notes & Instructions:</b><br/>{notes}", body_style))

    doc.build(story)
    return output_path


def generate_png_invoice(
    output_path: str,
    supplier_name: str,
    invoice_number: str,
    date_str: str,
    total_str: str
):
    """Generates a synthetic PNG invoice image."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw header banner
    draw.rectangle([(0, 0), (800, 80)], fill=(15, 23, 42))
    
    # Text drawing (using default bitmap font safely)
    draw.text((30, 28), "INVOICE - COMMERCIAL BILLING", fill=(255, 255, 255))
    draw.text((30, 110), f"SUPPLIER: {supplier_name}", fill=(15, 23, 42))
    draw.text((30, 140), f"INVOICE #: {invoice_number}", fill=(100, 116, 139))
    draw.text((30, 170), f"DATE: {date_str}", fill=(100, 116, 139))
    
    draw.line([(30, 210), (770, 210)], fill=(226, 232, 240), width=2)
    
    draw.text((30, 240), "Line 1: General Consulting & Hardware Package", fill=(30, 41, 59))
    draw.text((650, 240), f"${total_str}", fill=(30, 41, 59))
    
    draw.line([(30, 300), (770, 300)], fill=(226, 232, 240), width=2)
    draw.text((500, 330), f"TOTAL: ${total_str}", fill=(15, 23, 42))

    img.save(output_path, "PNG")
    return output_path
