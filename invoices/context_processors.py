from django.conf import settings
from invoices.models import Document, Invoice, ValidationIssue, ProcessingJob


def pipeline_status_processor(request):
    """Context processor exposing global pipeline metrics to navigation and sidebar."""
    if not request.user.is_authenticated:
        return {}

    pending_review_count = Document.objects.filter(
        status__in=['READY_FOR_REVIEW', 'FLAGGED_ISSUES']
    ).count()

    unresolved_exceptions_count = ValidationIssue.objects.filter(
        is_resolved=False
    ).count()

    pending_jobs_count = ProcessingJob.objects.filter(
        status__in=['PENDING', 'RUNNING']
    ).count()

    approved_unexported_count = Invoice.objects.filter(
        approval_status='APPROVED'
    ).exclude(accounting_export__status='SUCCESS').count()

    gemini_key_configured = bool(getattr(settings, 'GEMINI_API_KEY', ''))
    extraction_mode = getattr(settings, 'EXTRACTION_MODE', 'auto')

    return {
        'NAV_PENDING_REVIEW_COUNT': pending_review_count,
        'NAV_EXCEPTIONS_COUNT': unresolved_exceptions_count,
        'NAV_PENDING_JOBS_COUNT': pending_jobs_count,
        'NAV_APPROVED_UNEXPORTED_COUNT': approved_unexported_count,
        'GEMINI_KEY_CONFIGURED': gemini_key_configured,
        'EXTRACTION_MODE': extraction_mode,
    }
