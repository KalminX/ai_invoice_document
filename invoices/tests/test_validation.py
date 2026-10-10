from decimal import Decimal
import datetime
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from invoices.models import Document, Invoice, InvoiceLineItem, ValidationIssue, Supplier, AccountCode
from invoices.services.validation_service import ValidationService


class ValidationServiceTestCase(TestCase):
    def setUp(self):
        self.account_code = AccountCode.objects.create(
            code="6200", name="Cloud Hosting", category="EXPENSE"
        )
        self.supplier = Supplier.objects.create(
            name="Acme Cloud Services Inc.",
            default_account_code=self.account_code
        )

        dummy_file = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test invoice content", content_type="application/pdf")
        self.doc1 = Document.objects.create(
            original_filename="invoice_1.pdf",
            file=dummy_file,
            file_type="pdf",
            file_size=1024,
            file_hash="hash_1111111111111111111111111111111111111111111111111111111111111111",
            status="PROCESSING",
            confidence_score=0.95
        )

        self.valid_invoice = Invoice.objects.create(
            document=self.doc1,
            supplier=self.supplier,
            supplier_name_raw="Acme Cloud Services Inc.",
            invoice_number="INV-2026-001",
            invoice_date=datetime.date(2026, 9, 15),
            due_date=datetime.date(2026, 10, 15),
            currency="USD",
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("80.00"),
            total_amount=Decimal("1080.00")
        )
        InvoiceLineItem.objects.create(
            invoice=self.valid_invoice,
            line_number=1,
            description="Cloud Hosting Nodes",
            quantity=Decimal("1.00"),
            unit_price=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            account_code=self.account_code
        )

    def test_valid_invoice_passes_validation(self):
        """Tests that a clean invoice has 0 validation errors and sets status to READY_FOR_REVIEW."""
        issues = ValidationService.validate_invoice(self.valid_invoice)
        self.assertEqual(len(issues), 0)
        self.assertTrue(self.valid_invoice.is_math_valid)
        self.assertFalse(self.valid_invoice.has_blocking_issues)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.status, "READY_FOR_REVIEW")

    def test_arithmetic_mismatch_creates_blocking_issue(self):
        """Tests that subtotal + tax != total triggers an ARITHMETIC_MISMATCH blocking issue."""
        self.valid_invoice.total_amount = Decimal("1500.00")  # Incorrect (1000 + 80 = 1080)
        self.valid_invoice.save()

        issues = ValidationService.validate_invoice(self.valid_invoice)
        self.assertTrue(any(i.issue_type == 'ARITHMETIC_MISMATCH' and i.is_blocking for i in issues))
        self.assertFalse(self.valid_invoice.is_math_valid)
        self.assertTrue(self.valid_invoice.has_blocking_issues)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.status, "FLAGGED_ISSUES")

    def test_duplicate_file_hash_detection(self):
        """Tests that uploading an exact duplicate file hash flags DUPLICATE_HASH."""
        dummy_file2 = SimpleUploadedFile("test2.pdf", b"%PDF-1.4 test invoice content", content_type="application/pdf")
        doc2 = Document.objects.create(
            original_filename="duplicate.pdf",
            file=dummy_file2,
            file_type="pdf",
            file_size=1024,
            file_hash="hash_1111111111111111111111111111111111111111111111111111111111111111",  # Same hash
            status="PROCESSING"
        )
        inv2 = Invoice.objects.create(
            document=doc2,
            supplier=self.supplier,
            supplier_name_raw="Acme Cloud Services Inc.",
            invoice_number="INV-2026-002",
            invoice_date=datetime.date(2026, 9, 15),
            total_amount=Decimal("100.00"),
            subtotal=Decimal("100.00")
        )

        issues = ValidationService.validate_invoice(inv2)
        self.assertTrue(any(i.issue_type == 'DUPLICATE_HASH' and i.is_blocking for i in issues))

    def test_duplicate_supplier_and_invoice_number_detection(self):
        """Tests that matching supplier + invoice # flags DUPLICATE_NUMBER."""
        dummy_file3 = SimpleUploadedFile("test3.pdf", b"distinct content", content_type="application/pdf")
        doc3 = Document.objects.create(
            original_filename="invoice_3.pdf",
            file=dummy_file3,
            file_type="pdf",
            file_size=2048,
            file_hash="unique_hash_3333333333333333333333333333333333333333333333333333",
            status="PROCESSING"
        )
        inv3 = Invoice.objects.create(
            document=doc3,
            supplier=self.supplier,
            supplier_name_raw="Acme Cloud Services Inc.",
            invoice_number="INV-2026-001",  # Same invoice # as valid_invoice
            invoice_date=datetime.date(2026, 9, 15),
            total_amount=Decimal("500.00"),
            subtotal=Decimal("500.00")
        )

        issues = ValidationService.validate_invoice(inv3)
        self.assertTrue(any(i.issue_type == 'DUPLICATE_NUMBER' and i.is_blocking for i in issues))
        self.assertTrue(inv3.is_duplicate)
        self.assertEqual(inv3.duplicate_of, self.valid_invoice)

    def test_unknown_supplier_warning(self):
        """Tests that unrecognized vendor flags UNKNOWN_SUPPLIER warning."""
        self.valid_invoice.supplier = None
        self.valid_invoice.supplier_name_raw = "Unregistered Pilot Vendor Ltd"
        self.valid_invoice.save()

        issues = ValidationService.validate_invoice(self.valid_invoice)
        self.assertTrue(any(i.issue_type == 'UNKNOWN_SUPPLIER' and not i.is_blocking for i in issues))
        self.assertTrue(self.valid_invoice.is_unknown_supplier)
