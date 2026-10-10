from decimal import Decimal
from django.test import TestCase
from invoices.models import AccountCode, Supplier, Invoice, InvoiceLineItem, Document
from invoices.services.suggestion_service import AccountCodingSuggestionService


class AccountCodingSuggestionTestCase(TestCase):
    def setUp(self):
        self.acc_cloud = AccountCode.objects.create(code="6200", name="Cloud Infrastructure")
        self.acc_consulting = AccountCode.objects.create(code="6100", name="Consulting Services")
        self.acc_supplies = AccountCode.objects.create(code="5000", name="Office Supplies")

        self.supplier = Supplier.objects.create(
            name="Alpha Cloud Tech",
            default_account_code=self.acc_cloud
        )

    def test_suggests_supplier_configured_default(self):
        """Tests that supplier configured default account code is returned with high confidence."""
        acc, conf, reason = AccountCodingSuggestionService.suggest_for_line_item(
            description="Dedicated Kubernetes Node",
            supplier=self.supplier
        )
        self.assertEqual(acc, self.acc_cloud)
        self.assertGreaterEqual(conf, 0.90)
        self.assertIn("Configured default", reason)

    def test_suggests_from_historical_approved_invoices(self):
        """Tests learning from past approved line items."""
        supplier_no_default = Supplier.objects.create(name="Omega Advisory")
        
        # Create an approved historical invoice
        doc = Document.objects.create(
            original_filename="past.pdf", file_type="pdf", file_size=100, file_hash="hash_p", status="APPROVED"
        )
        past_inv = Invoice.objects.create(
            document=doc, supplier=supplier_no_default, invoice_number="P-1", approval_status="APPROVED",
            total_amount=Decimal("100.00")
        )
        InvoiceLineItem.objects.create(
            invoice=past_inv, description="Security Audit Q2", quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"), total_amount=Decimal("100.00"), account_code=self.acc_consulting
        )

        acc, conf, reason = AccountCodingSuggestionService.suggest_for_line_item(
            description="Security Audit Q3 Follow-up",
            supplier=supplier_no_default
        )
        self.assertEqual(acc, self.acc_consulting)
        self.assertGreaterEqual(conf, 0.80)

    def test_no_suggestion_fallback_does_not_hallucinate(self):
        """Tests that unknown items with no history explicitly return None."""
        new_sup = Supplier.objects.create(name="Brand New Mysterious Vendor")
        acc, conf, reason = AccountCodingSuggestionService.suggest_for_line_item(
            description="Xylophone calibration apparatus",
            supplier=new_sup
        )
        self.assertIsNone(acc)
        self.assertEqual(conf, 0.0)
        self.assertIn("manual", reason.lower())
