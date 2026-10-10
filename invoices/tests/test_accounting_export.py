from decimal import Decimal
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from invoices.models import Document, Invoice, InvoiceLineItem, AccountingExport, AccountCode, Supplier
from invoices.adapters.mock_adapter import MockAccountingAdapter


class AccountingExportTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='director', password='password123')
        self.acc = AccountCode.objects.create(code="6200", name="Cloud Tech")
        self.supplier = Supplier.objects.create(name="Acme Inc", default_account_code=self.acc)

        self.doc = Document.objects.create(
            original_filename="export_test.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="hash_export_test",
            status="APPROVED"
        )
        self.invoice = Invoice.objects.create(
            document=self.doc,
            supplier=self.supplier,
            invoice_number="EXP-001",
            invoice_date=datetime.date(2026, 9, 20),
            subtotal=Decimal("500.00"),
            tax_amount=Decimal("40.00"),
            total_amount=Decimal("540.00"),
            approval_status="PENDING"  # Initially not approved
        )
        self.adapter = MockAccountingAdapter()

    def test_cannot_export_unapproved_invoice(self):
        """Unapproved invoice must be rejected by accounting adapter."""
        result = self.adapter.export_invoice(self.invoice, user=self.user)
        self.assertFalse(result.success)
        self.assertIn("strictly required", result.error.lower())
        self.assertFalse(AccountingExport.objects.filter(invoice=self.invoice).exists())

    def test_export_approved_invoice_and_idempotency(self):
        """Approved invoice exports successfully; repeated calls are idempotent."""
        self.invoice.approval_status = 'APPROVED'
        self.invoice.save()

        # First Export
        result = self.adapter.export_invoice(self.invoice, user=self.user)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.external_bill_id)
        self.assertTrue(result.external_bill_id.startswith("MOCK-BILL-"))

        export_rec = AccountingExport.objects.get(invoice=self.invoice)
        self.assertEqual(export_rec.status, "SUCCESS")
        self.assertEqual(export_rec.external_bill_id, result.external_bill_id)

        # Second Export Attempt (Idempotency Check)
        result2 = self.adapter.export_invoice(self.invoice, user=self.user)
        self.assertTrue(result2.success)
        self.assertEqual(result2.external_bill_id, result.external_bill_id)
        self.assertEqual(result2.status, "ALREADY_EXPORTED")
        self.assertEqual(AccountingExport.objects.filter(invoice=self.invoice).count(), 1)
