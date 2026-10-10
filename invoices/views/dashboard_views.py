from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg
from invoices.models import Document, Invoice, ValidationIssue, AuditLog, AccountingExport


@login_required
def dashboard_view(request):
    """Financial Operations & Document Extraction Dashboard."""
    # Summary Metrics
    total_docs = Document.objects.count()
    pending_review = Document.objects.filter(status__in=['READY_FOR_REVIEW', 'FLAGGED_ISSUES']).count()
    flagged_issues_docs = Document.objects.filter(status='FLAGGED_ISSUES').count()
    approved_docs = Document.objects.filter(status='APPROVED').count()
    exported_docs = Document.objects.filter(status='EXPORTED').count()
    failed_docs = Document.objects.filter(status='FAILED').count()

    total_spend = Invoice.objects.filter(
        approval_status__in=['APPROVED', 'EXPORTED']
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    avg_confidence = Document.objects.filter(
        confidence_score__isnull=False
    ).aggregate(avg=Avg('confidence_score'))['avg']
    avg_conf_pct = int((avg_confidence or 0.0) * 100)

    # Exception breakdown
    unresolved_issues = ValidationIssue.objects.filter(is_resolved=False)
    math_errors = unresolved_issues.filter(issue_type__in=['ARITHMETIC_MISMATCH', 'LINE_ITEMS_MISMATCH', 'LINE_CALCULATION_MISMATCH']).count()
    duplicate_errors = unresolved_issues.filter(issue_type__in=['DUPLICATE_HASH', 'DUPLICATE_NUMBER']).count()
    unknown_suppliers = unresolved_issues.filter(issue_type='UNKNOWN_SUPPLIER').count()
    missing_fields = unresolved_issues.filter(issue_type='MISSING_FIELD').count()
    low_confidence = unresolved_issues.filter(issue_type='LOW_CONFIDENCE').count()

    # Recent Invoices
    recent_documents = Document.objects.select_related('invoice', 'uploaded_by').order_by('-created_at')[:8]

    # Recent Audit Activity
    recent_activities = AuditLog.objects.select_related('user', 'document', 'invoice').order_by('-created_at')[:10]

    context = {
        'total_docs': total_docs,
        'pending_review': pending_review,
        'flagged_issues_docs': flagged_issues_docs,
        'approved_docs': approved_docs,
        'exported_docs': exported_docs,
        'failed_docs': failed_docs,
        'total_spend': total_spend,
        'avg_conf_pct': avg_conf_pct,
        'math_errors': math_errors,
        'duplicate_errors': duplicate_errors,
        'unknown_suppliers': unknown_suppliers,
        'missing_fields': missing_fields,
        'low_confidence': low_confidence,
        'total_exceptions': unresolved_issues.count(),
        'recent_documents': recent_documents,
        'recent_activities': recent_activities,
    }

    return render(request, 'invoices/dashboard/dashboard.html', context)
