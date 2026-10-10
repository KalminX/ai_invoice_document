from decimal import Decimal
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from invoices.models import Document, Invoice, InvoiceLineItem, ValidationIssue, Supplier, AccountCode, AuditLog
from invoices.services.validation_service import ValidationService


class ReviewWorkflowTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', password='password123')
        self.client = Client()
        self.client.login(username='reviewer', password='password123')

        self.account_code = AccountCode.objects.create(code="6200", name="Cloud Hosting")
        self.supplier = Supplier.objects.create(name="Acme Cloud Services Inc.")

        self.doc = Document.objects.create(
            original_filename="review_test.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="hash_review_test",
            status="FLAGGED_ISSUES"
        )
        self.invoice = Invoice.objects.create(
            document=self.doc,
            supplier=self.supplier,
            supplier_name_raw="Acme Cloud Services Inc.",
            invoice_number="INV-REV-01",
            invoice_date=datetime.date(2026, 9, 10),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("10.00"),
            total_amount=Decimal("200.00"),  # Error: 100+10 != 200
            approval_status="PENDING"
        )
        # Create blocking issue
        self.issue = ValidationIssue.objects.create(
            document=self.doc,
            invoice=self.invoice,
            issue_type='ARITHMETIC_MISMATCH',
            severity='ERROR',
            message='Subtotal + tax mismatch',
            is_blocking=True,
            is_resolved=False
        )

    def test_cannot_approve_with_blocking_issues(self):
        """Approval endpoint must reject approving invoice when blocking issues exist."""
        approve_url = reverse('invoices:invoice_approve', kwargs={'invoice_id': self.invoice.id})
        response = self.client.post(approve_url, follow=True)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, 'PENDING')
        self.assertNotEqual(self.invoice.approval_status, 'APPROVED')

    def test_save_corrections_resolves_and_allows_approval(self):
        """Correcting values updates calculations, clears blocking issues, and enables approval."""
        save_url = reverse('invoices:invoice_save', kwargs={'invoice_id': self.invoice.id})
        post_data = {
            'supplier_id': self.supplier.id,
            'supplier_name_raw': 'Acme Cloud Services Inc.',
            'invoice_number': 'INV-REV-01',
            'currency': 'USD',
            'invoice_date': '2026-09-10',
            'subtotal': '100.00',
            'tax_amount': '10.00',
            'total_amount': '110.00',  # Fixed: 100+10 = 110
            'line_id[]': [],
            'line_description[]': ['Cloud Storage'],
            'line_quantity[]': ['1.00'],
            'line_unit_price[]': ['100.00'],
            'line_total[]': ['100.00'],
            'line_account_code[]': [self.account_code.id],
        }
        self.client.post(save_url, data=post_data, follow=True)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal('110.00'))
        self.assertTrue(self.invoice.can_approve)

        # Now approve
        approve_url = reverse('invoices:invoice_approve', kwargs={'invoice_id': self.invoice.id})
        response = self.client.post(approve_url, follow=True)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, 'APPROVED')
        self.assertEqual(self.invoice.approved_by, self.user)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'APPROVED')

        # Verify audit log exists
        audit_exists = AuditLog.objects.filter(
            invoice=self.invoice, action='INVOICE_APPROVED'
        ).exists()
        self.assertTrue(audit_exists)
