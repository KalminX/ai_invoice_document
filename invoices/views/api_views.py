import json
from decimal import Decimal
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from invoices.models import AccountCode, Supplier, ProcessingJob, Document
from invoices.services.suggestion_service import AccountCodingSuggestionService


@login_required
@require_http_methods(["GET"])
def api_suggest_account_code(request):
    """
    API endpoint to dynamically return account coding suggestions based on line item description
    and optional supplier ID or supplier name.
    """
    description = request.GET.get('description', '').strip()
    supplier_id = request.GET.get('supplier_id')
    supplier_name = request.GET.get('supplier_name', '')

    supplier = None
    if supplier_id and supplier_id.isdigit():
        supplier = Supplier.objects.filter(id=int(supplier_id)).first()

    suggested_acc, confidence, reason = AccountCodingSuggestionService.suggest_for_line_item(
        description=description,
        supplier=supplier,
        extracted_supplier_name=supplier_name
    )

    if suggested_acc:
        return JsonResponse({
            'has_suggestion': True,
            'account_id': suggested_acc.id,
            'account_code': suggested_acc.code,
            'account_name': suggested_acc.name,
            'confidence': confidence,
            'reason': reason
        })
    else:
        return JsonResponse({
            'has_suggestion': False,
            'account_id': None,
            'account_code': None,
            'account_name': None,
            'confidence': 0.0,
            'reason': reason
        })


@login_required
@require_http_methods(["GET"])
def api_job_status(request, job_id):
    """API endpoint to poll job processing status."""
    job = ProcessingJob.objects.filter(id=job_id).first()
    if not job:
        return JsonResponse({'error': 'Job not found'}, status=404)

    return JsonResponse({
        'job_id': job.id,
        'status': job.status,
        'job_type': job.job_type,
        'document_status': job.document.status,
        'attempts': job.attempts,
        'has_invoice': hasattr(job.document, 'invoice'),
        'invoice_id': job.document.invoice.id if hasattr(job.document, 'invoice') else None,
    })
