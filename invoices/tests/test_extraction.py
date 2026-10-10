from decimal import Decimal
import datetime
from django.test import TestCase
from invoices.services.schemas import InvoiceExtractionSchema, LineItemSchema
from invoices.services.mock_extractor import extract_with_mock


class ExtractionSchemaTestCase(TestCase):
    def test_pydantic_schema_validation_and_decimal_parsing(self):
        """Tests that currency strings and numbers are parsed into Python Decimal."""
        data = {
            "supplier_name": "Test Vendor LLC",
            "invoice_number": "INV-100",
            "invoice_date": "2026-09-01",
            "due_date": "2026-10-01",
            "currency": "$",
            "subtotal": "$1,250.50",
            "tax_amount": "100.00",
            "total_amount": "$1,350.50",
            "confidence_score": 0.95,
            "line_items": [
                {
                    "description": "Cloud Hosting Service",
                    "quantity": "2",
                    "unit_price": "$625.25",
                    "total_amount": "$1,250.50"
                }
            ]
        }
        schema = InvoiceExtractionSchema.model_validate(data)
        self.assertEqual(schema.currency, "USD")
        self.assertEqual(schema.subtotal, Decimal("1250.50"))
        self.assertEqual(schema.tax_amount, Decimal("100.00"))
        self.assertEqual(schema.total_amount, Decimal("1350.50"))
        self.assertEqual(len(schema.line_items), 1)
        self.assertEqual(schema.line_items[0].quantity, Decimal("2.00"))
        self.assertEqual(schema.line_items[0].unit_price, Decimal("625.25"))

    def test_mock_extractor_preset_scenarios(self):
        """Tests mock extractor presets for synthetic files."""
        res_acme = extract_with_mock("/fake/path/acme_cloud_invoice.pdf", "acme_cloud_invoice.pdf")
        self.assertEqual(res_acme.supplier_name, "Acme Cloud Services Inc.")
        self.assertEqual(res_acme.invoice_number, "INV-2026-0891")
        self.assertEqual(res_acme.total_amount, Decimal("2646.00"))

        res_math = extract_with_mock("/fake/path/math_error_invoice.pdf", "math_error_invoice.pdf")
        self.assertEqual(res_math.supplier_name, "Metro Office Supplies Co.")
        # subtotal 1500 + tax 120 != total 1850
        self.assertEqual(res_math.total_amount, Decimal("1850.00"))
        self.assertEqual(res_math.subtotal, Decimal("1500.00"))
