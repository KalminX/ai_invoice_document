import logging
import traceback
from django.utils import timezone
from ..models import ProcessingJob, Document
from .extraction_service import ExtractionService

logger = logging.getLogger('invoices')


class JobService:
    """Service for enqueueing and executing database-backed background jobs."""

    @classmethod
    def enqueue_extraction(cls, document: Document) -> ProcessingJob:
        """Enqueues an extraction & validation job for a newly uploaded document."""
        document.status = 'QUEUED'
        document.save(update_fields=['status'])

        job = ProcessingJob.objects.create(
            document=document,
            job_type='EXTRACT_AND_VALIDATE',
            status='PENDING',
            scheduled_at=timezone.now()
        )
        logger.info(f"Enqueued ProcessingJob #{job.id} for Document #{document.id} ({document.original_filename})")
        return job

    @classmethod
    def execute_job(cls, job: ProcessingJob) -> bool:
        """Executes a single processing job with retry logic."""
        job.status = 'RUNNING'
        job.started_at = timezone.now()
        job.attempts += 1
        job.save(update_fields=['status', 'started_at', 'attempts'])

        try:
            if job.job_type == 'EXTRACT_AND_VALIDATE':
                ExtractionService.process_document(job.document, user=job.document.uploaded_by)
            elif job.job_type == 'EXPORT_ACCOUNTING':
                from ..adapters.factory import get_accounting_adapter
                adapter = get_accounting_adapter()
                if hasattr(job.document, 'invoice'):
                    adapter.export_invoice(job.document.invoice, user=job.document.uploaded_by)

            job.status = 'COMPLETED'
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'completed_at'])
            logger.info(f"Job #{job.id} ({job.job_type}) completed successfully.")
            return True

        except Exception as e:
            tb = traceback.format_exc()
            job.error_log = f"{str(e)}\n\n{tb}"
            if job.attempts < job.max_attempts:
                job.status = 'PENDING'  # Retry on next loop
                logger.warning(f"Job #{job.id} failed attempt {job.attempts}/{job.max_attempts}. Will retry. Error: {e}")
            else:
                job.status = 'FAILED'
                logger.error(f"Job #{job.id} permanently failed after {job.attempts} attempts. Error: {e}")
            job.save(update_fields=['status', 'error_log'])
            return False

    @classmethod
    def process_pending_batch(cls, limit: int = 10) -> int:
        """Processes up to `limit` pending jobs."""
        pending_jobs = ProcessingJob.objects.filter(
            status='PENDING',
            scheduled_at__lte=timezone.now()
        ).order_by('scheduled_at')[:limit]

        count = 0
        for job in pending_jobs:
            cls.execute_job(job)
            count += 1
        return count
