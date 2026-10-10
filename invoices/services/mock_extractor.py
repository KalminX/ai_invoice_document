import re
import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from .schemas import InvoiceExtractionSchema, LineItemSchema


SAMPLE_PRESETS = {
    "acme": {
        "supplier_name": "Acme Cloud Services Inc.",
        "tax_id": "US-987654321",
        "invoice_number": "INV-2026-0891",
        "invoice_date": datetime.date(2026, 9, 15),
        "due_date": datetime.date(2026, 10, 15),
        "currency": "USD",
        "subtotal": Decimal("2450.00"),
        "tax_amount": Decimal("196.00"),
        "total_amount": Decimal("2646.00"),
        "confidence_score": 0.98,
        "notes": "Net 30 payment terms. Wire transfer or ACH.",
        "line_items": [
            LineItemSchema(
                description="Enterprise Cloud Cluster (16 Nodes) - Monthly Subscription",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1800.00"),
                total_amount=Decimal("1800.00"),
                account_code="6200"
            ),
            LineItemSchema(
                description="Managed PostgreSQL Database Multi-AZ Replication",
                quantity=Decimal("1.00"),
                unit_price=Decimal("450.00"),
                total_amount=Decimal("450.00"),
                account_code="6200"
            ),
            LineItemSchema(
                description="Premium 24/7 SLA Support Tier",
                quantity=Decimal("1.00"),
                unit_price=Decimal("200.00"),
                total_amount=Decimal("200.00"),
                account_code="6200"
            ),
        ]
    },
    "apex": {
        "supplier_name": "Apex Global Advisors LLC",
        "tax_id": "US-123456789",
        "invoice_number": "AGA-2026-4402",
        "invoice_date": datetime.date(2026, 9, 20),
        "due_date": datetime.date(2026, 10, 20),
        "currency": "USD",
        "subtotal": Decimal("4800.00"),
        "tax_amount": Decimal("0.00"),
        "total_amount": Decimal("4800.00"),
        "confidence_score": 0.95,
        "notes": "Professional consulting services rendered for Q3 Architecture Review.",
        "line_items": [
            LineItemSchema(
                description="Senior Technical Advisory - Systems Architecture (24 hrs @ $150/hr)",
                quantity=Decimal("24.00"),
                unit_price=Decimal("150.00"),
                total_amount=Decimal("3600.00"),
                account_code="6100"
            ),
            LineItemSchema(
                description="Security & Compliance Audit Review",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1200.00"),
                total_amount=Decimal("1200.00"),
                account_code="6100"
            ),
        ]
    },
    "math_error": {
        "supplier_name": "Metro Office Supplies Co.",
        "tax_id": "US-554433221",
        "invoice_number": "MOS-99120",
        "invoice_date": datetime.date(2026, 9, 28),
        "due_date": datetime.date(2026, 10, 28),
        "currency": "USD",
        "subtotal": Decimal("1500.00"),
        "tax_amount": Decimal("120.00"),
        "total_amount": Decimal("1850.00"),  # Intentionally incorrect (1500+120=1620, not 1850)
        "confidence_score": 0.92,
        "notes": "Bulk stationery & ergonomic workstation equipment.",
        "line_items": [
            LineItemSchema(
                description="Ergonomic Executive Mesh Chairs",
                quantity=Decimal("3.00"),
                unit_price=Decimal("350.00"),
                total_amount=Decimal("1050.00"),
                account_code="5000"
            ),
            LineItemSchema(
                description="Recycled Laser Printer Paper (10 Cartons)",
                quantity=Decimal("10.00"),
                unit_price=Decimal("45.00"),
                total_amount=Decimal("450.00"),
                account_code="5000"
            ),
        ]
    },
    "duplicate": {
        "supplier_name": "Acme Cloud Services Inc.",
        "tax_id": "US-987654321",
        "invoice_number": "INV-2026-0891",  # Same as Acme preset
        "invoice_date": datetime.date(2026, 9, 15),
        "due_date": datetime.date(2026, 10, 15),
        "currency": "USD",
        "subtotal": Decimal("2450.00"),
        "tax_amount": Decimal("196.00"),
        "total_amount": Decimal("2646.00"),
        "confidence_score": 0.98,
        "notes": "Duplicate billing submission for validation testing.",
        "line_items": [
            LineItemSchema(
                description="Enterprise Cloud Cluster (16 Nodes) - Monthly Subscription",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1800.00"),
                total_amount=Decimal("1800.00"),
                account_code="6200"
            ),
            LineItemSchema(
                description="Managed PostgreSQL Database Multi-AZ Replication",
                quantity=Decimal("1.00"),
                unit_price=Decimal("450.00"),
                total_amount=Decimal("450.00"),
                account_code="6200"
            ),
            LineItemSchema(
                description="Premium 24/7 SLA Support Tier",
                quantity=Decimal("1.00"),
                unit_price=Decimal("200.00"),
                total_amount=Decimal("200.00"),
                account_code="6200"
            ),
        ]
    },
    "unknown_supplier": {
        "supplier_name": "Vanguard Quantum Robotics Ltd",
        "tax_id": "GB-998877665",
        "invoice_number": "VQR-88210",
        "invoice_date": datetime.date(2026, 10, 1),
        "due_date": datetime.date(2026, 10, 31),
        "currency": "USD",
        "subtotal": Decimal("3200.00"),
        "tax_amount": Decimal("256.00"),
        "total_amount": Decimal("3456.00"),
        "confidence_score": 0.91,
        "notes": "Experimental hardware unit pilot.",
        "line_items": [
            LineItemSchema(
                description="Quantum Sensor Development Kit v2",
                quantity=Decimal("2.00"),
                unit_price=Decimal("1600.00"),
                total_amount=Decimal("3200.00"),
                account_code=None
            )
        ]
    },
    "missing_fields": {
        "supplier_name": None,  # Missing supplier
        "tax_id": None,
        "invoice_number": None,  # Missing invoice number
        "invoice_date": datetime.date(2026, 10, 5),
        "due_date": None,
        "currency": "USD",
        "subtotal": Decimal("850.00"),
        "tax_amount": Decimal("0.00"),
        "total_amount": Decimal("850.00"),
        "confidence_score": 0.45,  # Low confidence
        "notes": "Receipt snippet with damaged header area.",
        "line_items": [
            LineItemSchema(
                description="Miscellaneous Hardware Components",
                quantity=Decimal("1.00"),
                unit_price=Decimal("850.00"),
                total_amount=Decimal("850.00"),
                account_code=None
            )
        ]
    },
    "low_confidence": {
        "supplier_name": "Blurry Scan Vendor Co",
        "tax_id": "US-001122",
        "invoice_number": "BLUR-001",
        "invoice_date": datetime.date(2026, 10, 2),
        "due_date": datetime.date(2026, 10, 16),
        "currency": "USD",
        "subtotal": Decimal("640.00"),
        "tax_amount": Decimal("51.20"),
        "total_amount": Decimal("691.20"),
        "confidence_score": 0.58,  # Below 0.80 threshold
        "notes": "Low resolution image scan detected.",
        "line_items": [
            LineItemSchema(
                description="General Supplies (Unverified line item)",
                quantity=Decimal("1.00"),
                unit_price=Decimal("640.00"),
                total_amount=Decimal("640.00"),
                account_code=None
            )
        ]
    }
}


def extract_with_mock(file_path: str, original_filename: str) -> InvoiceExtractionSchema:
    """
    Extracts high-fidelity structured invoice data offline using deterministic preset matching
    or synthetic OCR extraction for demonstration and testing without API costs.
    """
    fn_lower = original_filename.lower()
    
    # Try matching preset keywords in filename
    for key, data in SAMPLE_PRESETS.items():
        if key in fn_lower:
            return InvoiceExtractionSchema(**data)

    # Check if PDF contains detectable keywords
    if file_path.lower().endswith('.pdf'):
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            extracted_text = " ".join([page.extract_text() or "" for page in reader.pages]).lower()
            
            for key, data in SAMPLE_PRESETS.items():
                if key in extracted_text or (data["supplier_name"] and data["supplier_name"].lower() in extracted_text):
                    return InvoiceExtractionSchema(**data)
        except Exception:
            pass

    # Generic realistic fallback extraction for arbitrary uploads
    today = datetime.date.today()
    return InvoiceExtractionSchema(
        supplier_name="Apex Global Advisors LLC",
        tax_id="US-123456789",
        invoice_number=f"INV-{abs(hash(original_filename)) % 100000:05d}",
        invoice_date=today,
        due_date=today + datetime.timedelta(days=30),
        currency="USD",
        subtotal=Decimal("1250.00"),
        tax_amount=Decimal("100.00"),
        total_amount=Decimal("1350.00"),
        confidence_score=0.96,
        notes="Generated via Mock Extraction Engine for offline demonstration.",
        line_items=[
            LineItemSchema(
                description=f"Professional Services rendered ({original_filename})",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1250.00"),
                total_amount=Decimal("1250.00"),
                account_code="6100"
            )
        ]
    )
