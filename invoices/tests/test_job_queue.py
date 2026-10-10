from decimal import Decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from invoices.models import Document, ProcessingJob, Invoice
from invoices.services.job_service import JobService


class JobQueueTestCase(TestCase):
    def test_background_job_enqueue_and_execution(self):
        """Tests that enqueueing a document creates a job and JobService executes extraction."""
        dummy_file = SimpleUploadedFile("job_invoice.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
        doc = Document.objects.create(
            original_filename="acme_cloud_invoice.pdf",
            file=dummy_file,
            file_type="pdf",
            file_size=500,
            file_hash="hash_job_test",
            status="UPLOADED"
        )

        job = JobService.enqueue_extraction(doc)
        self.assertEqual(job.status, "PENDING")
        self.assertEqual(doc.status, "QUEUED")

        # Process pending batch
        processed_count = JobService.process_pending_batch(limit=10)
        self.assertEqual(processed_count, 1)

        job.refresh_from_db()
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.attempts, 1)
        
        doc.refresh_from_db()
        self.assertTrue(hasattr(doc, 'invoice'))
        self.assertIn(doc.status, ['READY_FOR_REVIEW', 'FLAGGED_ISSUES'])

    def test_management_command_process_jobs_batch(self):
        """Tests executing the process_jobs management command."""
        dummy_file = SimpleUploadedFile("cmd_invoice.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
        doc = Document.objects.create(
            original_filename="apex_consulting_invoice.pdf",
            file=dummy_file,
            file_type="pdf",
            file_size=500,
            file_hash="hash_cmd_test",
            status="UPLOADED"
        )
        job = JobService.enqueue_extraction(doc)
        
        call_command('process_jobs', limit=5)
        
        job.refresh_from_db()
        self.assertEqual(job.status, 'COMPLETED')
