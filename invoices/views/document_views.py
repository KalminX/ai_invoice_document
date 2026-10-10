import os
import logging
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods

from invoices.models import Document, Invoice, ProcessingJob, ValidationIssue
from invoices.services.extraction_service import ExtractionService
from invoices.services.job_service import JobService
from invoices.services.audit_service import AuditService

logger = logging.getLogger('invoices')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpeg', 'jpg'}


@login_required
def document_list_view(request):
    """Document repository listing with search, filtering, and pagination."""
    status_filter = request.GET.get('status', 'ALL')
    search_query = request.GET.get('q', '').strip()
    
    docs = Document.objects.select_related('invoice', 'uploaded_by').order_by('-created_at')

    if status_filter and status_filter != 'ALL':
        docs = docs.filter(status=status_filter)

    if search_query:
        docs = docs.filter(
            Q(original_filename__icontains=search_query) |
            Q(invoice__invoice_number__icontains=search_query) |
            Q(invoice__supplier_name_raw__icontains=search_query) |
            Q(invoice__supplier__name__icontains=search_query)
        )

    paginator = Paginator(docs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'current_status': status_filter,
        'search_query': search_query,
        'total_count': docs.count(),
        'status_choices': Document.STATUS_CHOICES,
    }
    return render(request, 'invoices/documents/document_list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def document_upload_view(request):
    """Document intake upload view with validation and instant or async queueing."""
    if request.method == "POST":
        uploaded_file = request.FILES.get('document_file')
        process_mode = request.POST.get('process_mode', 'instant')  # 'instant' or 'async_queue'
        force_engine = request.POST.get('force_engine', '')  # 'mock' or 'gemini' or ''

        if not uploaded_file:
            messages.error(request, "Please select an invoice document to upload.")
            return render(request, 'invoices/documents/document_upload.html')

        # 1. File Size Validation
        max_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 10) * 1024 * 1024
        if uploaded_file.size > max_bytes:
            messages.error(request, f"File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB.")
            return render(request, 'invoices/documents/document_upload.html')

        # 2. File Extension Validation
        ext = uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else ''
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(request, f"Invalid file format '.{ext}'. Supported formats are: PDF, PNG, JPEG.")
            return render(request, 'invoices/documents/document_upload.html')

        # 3. Calculate File SHA-256 Hash
        file_hash = Document.calculate_file_hash(uploaded_file)

        # 4. Save Document Record
        doc = Document.objects.create(
            original_filename=uploaded_file.name,
            file_type=ext,
            file_size=uploaded_file.size,
            file_hash=file_hash,
            uploaded_by=request.user,
            status='UPLOADED'
        )
        doc.file.save(uploaded_file.name, uploaded_file, save=True)

        AuditService.log(
            action='UPLOAD',
            description=f"Uploaded document '{uploaded_file.name}' ({uploaded_file.size / 1024:.1f} KB)",
            document=doc,
            user=request.user,
            details={'file_size': uploaded_file.size, 'file_hash': file_hash}
        )

        # 5. Process Synchronously or Enqueue in Background
        if process_mode == 'async_queue':
            job = JobService.enqueue_extraction(doc)
            messages.success(
                request, 
                f"Document '{doc.original_filename}' uploaded and queued for background processing (Job #{job.id}). "
                f"You can monitor it in the Processing Jobs queue."
            )
            return redirect('invoices:document_list')
        else:
            # Instant processing inside web request
            try:
                invoice = ExtractionService.process_document(
                    doc, 
                    user=request.user, 
                    force_mode=force_engine if force_engine in ('gemini', 'mock') else None
                )
                if invoice.has_blocking_issues:
                    messages.warning(
                        request,
                        f"Document processed with AI extraction. Validation flagged issues requiring your review."
                    )
                else:
                    messages.success(
                        request,
                        f"Document successfully extracted! Invoice #{invoice.invoice_number or 'N/A'} is ready for review."
                    )
                return redirect('invoices:invoice_review', invoice_id=invoice.id)
            except Exception as e:
                messages.error(request, f"Extraction failed: {str(e)}")
                return redirect('invoices:document_list')

    # GET request - load sample fixtures for quick testing convenience
    fixtures_dir = Path(settings.MEDIA_ROOT) / 'fixtures'
    sample_files = []
    if fixtures_dir.exists():
        for f in fixtures_dir.glob("*.*"):
            sample_files.append({
                'name': f.name,
                'path': f.name,
                'size': f"{f.stat().st_size / 1024:.1f} KB"
            })

    return render(request, 'invoices/documents/document_upload.html', {'sample_files': sample_files})


@login_required
@require_http_methods(["POST"])
def document_reprocess_view(request, document_id):
    """Re-runs extraction and validation on an existing document."""
    doc = get_object_or_404(Document, id=document_id)
    force_mode = request.POST.get('force_mode')
    
    try:
        invoice = ExtractionService.process_document(
            doc, 
            user=request.user, 
            force_mode=force_mode if force_mode in ('gemini', 'mock') else None
        )
        messages.success(request, f"Document '{doc.original_filename}' successfully reprocessed.")
        return redirect('invoices:invoice_review', invoice_id=invoice.id)
    except Exception as e:
        messages.error(request, f"Reprocessing failed: {str(e)}")
        return redirect('invoices:document_list')


@login_required
@require_http_methods(["POST"])
def document_delete_view(request, document_id):
    """Safely deletes document and cascades related models."""
    doc = get_object_or_404(Document, id=document_id)
    fn = doc.original_filename
    
    AuditService.log(
        action='FIELD_UPDATED',
        description=f"Deleted document '{fn}'",
        user=request.user
    )
    doc.delete()
    messages.success(request, f"Document '{fn}' was deleted successfully.")
    return redirect('invoices:document_list')
