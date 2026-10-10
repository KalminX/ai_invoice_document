from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from invoices.models import ValidationIssue, Document, Invoice


@login_required
def exception_queue_view(request):
    """
    Dedicated Exception Queue Dashboard.
    Enables AP specialists to filter, inspect, and take action on specific categories of anomalies.
    """
    category_filter = request.GET.get('category', 'ALL')
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'UNRESOLVED')  # 'UNRESOLVED', 'RESOLVED', 'ALL'

    issues_qs = ValidationIssue.objects.select_related(
        'document', 'invoice', 'invoice__supplier', 'resolved_by'
    ).order_by('-created_at')

    # Status filter
    if status_filter == 'UNRESOLVED':
        issues_qs = issues_qs.filter(is_resolved=False)
    elif status_filter == 'RESOLVED':
        issues_qs = issues_qs.filter(is_resolved=True)

    # Category filter
    if category_filter == 'ARITHMETIC':
        issues_qs = issues_qs.filter(
            issue_type__in=['ARITHMETIC_MISMATCH', 'LINE_ITEMS_MISMATCH', 'LINE_CALCULATION_MISMATCH']
        )
    elif category_filter == 'DUPLICATES':
        issues_qs = issues_qs.filter(
            issue_type__in=['DUPLICATE_HASH', 'DUPLICATE_NUMBER']
        )
    elif category_filter == 'UNKNOWN_SUPPLIER':
        issues_qs = issues_qs.filter(issue_type='UNKNOWN_SUPPLIER')
    elif category_filter == 'MISSING_FIELDS':
        issues_qs = issues_qs.filter(issue_type='MISSING_FIELD')
    elif category_filter == 'LOW_CONFIDENCE':
        issues_qs = issues_qs.filter(issue_type='LOW_CONFIDENCE')
    elif category_filter == 'FAILED':
        issues_qs = issues_qs.filter(issue_type__in=['EXTRACTION_FAILED', 'FILE_CORRUPT'])

    # Search filter
    if search_query:
        issues_qs = issues_qs.filter(
            Q(message__icontains=search_query) |
            Q(document__original_filename__icontains=search_query) |
            Q(invoice__invoice_number__icontains=search_query) |
            Q(invoice__supplier_name_raw__icontains=search_query)
        )

    # Compute category badge counts (for active unresolved items)
    base_unresolved = ValidationIssue.objects.filter(is_resolved=False)
    counts = {
        'ALL': base_unresolved.count(),
        'ARITHMETIC': base_unresolved.filter(issue_type__in=['ARITHMETIC_MISMATCH', 'LINE_ITEMS_MISMATCH', 'LINE_CALCULATION_MISMATCH']).count(),
        'DUPLICATES': base_unresolved.filter(issue_type__in=['DUPLICATE_HASH', 'DUPLICATE_NUMBER']).count(),
        'UNKNOWN_SUPPLIER': base_unresolved.filter(issue_type='UNKNOWN_SUPPLIER').count(),
        'MISSING_FIELDS': base_unresolved.filter(issue_type='MISSING_FIELD').count(),
        'LOW_CONFIDENCE': base_unresolved.filter(issue_type='LOW_CONFIDENCE').count(),
        'FAILED': base_unresolved.filter(issue_type__in=['EXTRACTION_FAILED', 'FILE_CORRUPT']).count(),
    }

    paginator = Paginator(issues_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'current_category': category_filter,
        'current_status': status_filter,
        'search_query': search_query,
        'counts': counts,
    }
    return render(request, 'invoices/exceptions/exception_queue.html', context)
