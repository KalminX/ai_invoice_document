import io
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from invoices.models import Document, Invoice, Supplier, AccountCode, ValidationIssue, ProcessingJob


class ViewsIntegrationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='password123', is_superuser=True)
        self.client = Client()
        self.client.login(username='admin', password='password123')

        self.account_code = AccountCode.objects.create(code="6200", name="Cloud Tech")
        self.supplier = Supplier.objects.create(name="Acme Cloud Services Inc.", default_account_code=self.account_code)

    def test_dashboard_view_renders_correctly(self):
        """Dashboard renders with status metrics."""
        response = self.client.get(reverse('invoices:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financial Pipeline Dashboard")
        self.assertContains(response, "Total Spend Extracted")

    def test_document_list_and_filters(self):
        """Document repository renders with filters."""
        response = self.client.get(reverse('invoices:document_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invoices & Documents Repository")

    def test_upload_invalid_file_extension_rejected(self):
        """Uploading .exe or .txt file is rejected with error message."""
        bad_file = SimpleUploadedFile("malicious.exe", b"binary content", content_type="application/octet-stream")
        response = self.client.post(
            reverse('invoices:document_upload'),
            data={'document_file': bad_file, 'process_mode': 'instant'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid file format")
        self.assertEqual(Document.objects.count(), 0)

    def test_upload_valid_pdf_instant_mode(self):
        """Uploading valid PDF invoice processes and extracts invoice."""
        pdf_file = SimpleUploadedFile("acme_cloud_invoice.pdf", b"%PDF-1.4 test invoice", content_type="application/pdf")
        response = self.client.post(
            reverse('invoices:document_upload'),
            data={'document_file': pdf_file, 'process_mode': 'instant', 'force_engine': 'mock'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Document.objects.count(), 1)
        doc = Document.objects.first()
        self.assertTrue(hasattr(doc, 'invoice'))
        self.assertEqual(doc.invoice.supplier_name_raw, "Acme Cloud Services Inc.")

    def test_upload_valid_pdf_async_queue_mode(self):
        """Uploading with async mode creates a queued ProcessingJob."""
        pdf_file = SimpleUploadedFile("async_test.pdf", b"%PDF-1.4 async invoice", content_type="application/pdf")
        response = self.client.post(
            reverse('invoices:document_upload'),
            data={'document_file': pdf_file, 'process_mode': 'async_queue'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProcessingJob.objects.count(), 1)
        job = ProcessingJob.objects.first()
        self.assertEqual(job.status, "PENDING")

    def test_api_suggest_account_endpoint(self):
        """API returns dynamic account suggestions for description."""
        url = reverse('invoices:api_suggest_account')
        response = self.client.get(f"{url}?description=Dedicated+Cloud+Cluster&supplier_id={self.supplier.id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['has_suggestion'])
        self.assertEqual(data['account_code'], '6200')

    def test_exception_queue_view(self):
        """Exception queue view renders and filters."""
        response = self.client.get(reverse('invoices:exception_queue'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exception Queue & Triage")

    def test_accounting_ledger_view(self):
        """Accounting ledger view renders."""
        response = self.client.get(reverse('invoices:export_ledger'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "General Ledger Accounting Integrations")
