import json
from decimal import Decimal
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from invoices.models import Invoice, InvoiceLineItem, ValidationIssue, Supplier, AccountCode, AuditLog
from invoices.services.validation_service import ValidationService
from invoices.services.suggestion_service import AccountCodingSuggestionService
from invoices.services.audit_service import AuditService
from invoices.adapters.factory import get_accounting_adapter


@login_required
def invoice_review_view(request, invoice_id):
    """Split-screen Human Review and Validation Workspace."""
    invoice = get_object_or_404(
        Invoice.objects.select_related('document', 'supplier', 'approved_by')
        .prefetch_related('line_items__account_code', 'line_items__suggested_account_code', 'validation_issues'),
        id=invoice_id
    )
    document = invoice.document

    suppliers = Supplier.objects.all().order_by('name')
    account_codes = AccountCode.objects.filter(is_active=True).order_by('code')
    validation_issues = invoice.validation_issues.all().order_by('-severity', 'is_resolved')
    audit_logs = invoice.audit_logs.select_related('user').order_by('-created_at')

    context = {
        'invoice': invoice,
        'document': document,
        'suppliers': suppliers,
        'account_codes': account_codes,
        'validation_issues': validation_issues,
        'audit_logs': audit_logs,
        'unresolved_blocking_count': invoice.blocking_issues_count,
        'can_approve': invoice.can_approve,
        'can_export': invoice.can_export,
    }
    return render(request, 'invoices/review/review_detail.html', context)


@login_required
@require_http_methods(["POST"])
def invoice_save_view(request, invoice_id):
    """Saves user edits to invoice header and line items, re-running validation checks."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    doc = invoice.document

    # Capture state before edits for audit diff
    old_data = {
        'invoice_number': invoice.invoice_number,
        'supplier_name': invoice.supplier_name_raw,
        'subtotal': str(invoice.subtotal),
        'tax_amount': str(invoice.tax_amount),
        'total_amount': str(invoice.total_amount),
        'currency': invoice.currency,
        'invoice_date': str(invoice.invoice_date) if invoice.invoice_date else None,
        'due_date': str(invoice.due_date) if invoice.due_date else None,
    }

    # 1. Update Header Fields
    supplier_id = request.POST.get('supplier_id')
    supplier_name_raw = request.POST.get('supplier_name_raw', '').strip()
    invoice.supplier_name_raw = supplier_name_raw

    if supplier_id and supplier_id != 'new':
        invoice.supplier = Supplier.objects.filter(id=supplier_id).first()
    else:
        # Create new supplier if requested
        if supplier_name_raw and request.POST.get('create_new_supplier') == 'on':
            new_sup, _ = Supplier.objects.get_or_create(
                name=supplier_name_raw,
                defaults={'is_approved': True}
            )
            invoice.supplier = new_sup
        else:
            invoice.supplier = None

    invoice.invoice_number = request.POST.get('invoice_number', '').strip()
    invoice.currency = request.POST.get('currency', 'USD').strip().upper()
    
    inv_date_str = request.POST.get('invoice_date')
    if inv_date_str:
        try:
            invoice.invoice_date = datetime.datetime.strptime(inv_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    else:
        invoice.invoice_date = None

    due_date_str = request.POST.get('due_date')
    if due_date_str:
        try:
            invoice.due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    else:
        invoice.due_date = None

    try:
        invoice.subtotal = Decimal(request.POST.get('subtotal', '0.00').replace(',', ''))
    except Exception:
        invoice.subtotal = Decimal('0.00')

    try:
        invoice.tax_amount = Decimal(request.POST.get('tax_amount', '0.00').replace(',', ''))
    except Exception:
        invoice.tax_amount = Decimal('0.00')

    try:
        invoice.total_amount = Decimal(request.POST.get('total_amount', '0.00').replace(',', ''))
    except Exception:
        invoice.total_amount = Decimal('0.00')

    invoice.notes = request.POST.get('notes', '')
    invoice.save()

    # 2. Update Line Items
    line_ids = request.POST.getlist('line_id[]')
    descriptions = request.POST.getlist('line_description[]')
    quantities = request.POST.getlist('line_quantity[]')
    unit_prices = request.POST.getlist('line_unit_price[]')
    totals = request.POST.getlist('line_total[]')
    account_code_ids = request.POST.getlist('line_account_code[]')

    processed_line_ids = []
    
    for i in range(len(descriptions)):
        desc = descriptions[i].strip()
        if not desc and i >= len(line_ids):
            continue  # Skip empty new row

        try:
            qty = Decimal(str(quantities[i]).replace(',', ''))
        except Exception:
            qty = Decimal('1.00')

        try:
            price = Decimal(str(unit_prices[i]).replace(',', ''))
        except Exception:
            price = Decimal('0.00')

        try:
            line_tot = Decimal(str(totals[i]).replace(',', ''))
            if line_tot == Decimal('0.00') and price > Decimal('0.00'):
                line_tot = round(qty * price, 2)
        except Exception:
            line_tot = round(qty * price, 2)

        acc_code = None
        if i < len(account_code_ids) and account_code_ids[i]:
            acc_code = AccountCode.objects.filter(id=account_code_ids[i]).first()

        cur_line_id = line_ids[i] if i < len(line_ids) and line_ids[i] else None

        if cur_line_id:
            line_obj = InvoiceLineItem.objects.filter(id=cur_line_id, invoice=invoice).first()
            if line_obj:
                line_obj.line_number = i + 1
                line_obj.description = desc
                line_obj.quantity = qty
                line_obj.unit_price = price
                line_obj.total_amount = line_tot
                line_obj.account_code = acc_code
                line_obj.save()
                processed_line_ids.append(line_obj.id)
        else:
            # Create new line item
            suggested_acc, conf, reason = AccountCodingSuggestionService.suggest_for_line_item(
                description=desc,
                supplier=invoice.supplier,
                extracted_supplier_name=invoice.supplier_name_raw
            )
            new_line = InvoiceLineItem.objects.create(
                invoice=invoice,
                line_number=i + 1,
                description=desc,
                quantity=qty,
                unit_price=price,
                total_amount=line_tot,
                account_code=acc_code or suggested_acc,
                suggested_account_code=suggested_acc,
                suggestion_confidence=conf if suggested_acc else None,
                suggestion_reason=reason
            )
            processed_line_ids.append(new_line.id)

    # Delete removed lines
    invoice.line_items.exclude(id__in=processed_line_ids).delete()

    # 3. Re-run Independent Validation
    issues = ValidationService.validate_invoice(invoice)

    # 4. Audit Log
    AuditService.log(
        action='FIELD_UPDATED',
        description=f"User updated invoice #{invoice.invoice_number} details and line items. Re-validated {len(issues)} issue(s).",
        invoice=invoice,
        user=request.user,
        details={'previous': old_data, 'active_issues': len(issues)}
    )

    messages.success(request, "Invoice changes saved and calculations re-validated successfully.")
    return redirect('invoices:invoice_review', invoice_id=invoice.id)


@login_required
@require_http_methods(["POST"])
def issue_resolve_view(request, issue_id):
    """Resolves or acknowledges an individual validation issue."""
    issue = get_object_or_404(ValidationIssue, id=issue_id)
    invoice = issue.invoice
    
    notes = request.POST.get('resolution_notes', 'Verified and manually acknowledged by reviewer.')
    issue.is_resolved = True
    issue.resolved_by = request.user
    issue.resolved_at = timezone.now()
    issue.resolution_notes = notes
    issue.save()

    # Re-evaluate invoice blocking status
    unresolved_blocking = invoice.validation_issues.filter(is_blocking=True, is_resolved=False).count()
    invoice.has_blocking_issues = (unresolved_blocking > 0)
    invoice.save(update_fields=['has_blocking_issues'])

    if not invoice.has_blocking_issues and invoice.document.status == 'FLAGGED_ISSUES':
        invoice.document.status = 'READY_FOR_REVIEW'
        invoice.document.save(update_fields=['status'])

    AuditService.log(
        action='ISSUE_RESOLVED',
        description=f"Resolved issue [{issue.get_issue_type_display()}]: {notes}",
        invoice=invoice,
        user=request.user,
        details={'issue_id': issue.id, 'issue_type': issue.issue_type}
    )

    messages.success(request, f"Validation issue '{issue.get_issue_type_display()}' was acknowledged and resolved.")
    return redirect('invoices:invoice_review', invoice_id=invoice.id)


@login_required
@require_http_methods(["POST"])
def invoice_approve_view(request, invoice_id):
    """Approves an invoice if all blocking checks pass."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    doc = invoice.document

    if not invoice.can_approve:
        blocking_issues = invoice.validation_issues.filter(is_blocking=True, is_resolved=False)
        issues_list = ", ".join([i.get_issue_type_display() for i in blocking_issues])
        messages.error(
            request, 
            f"Approval Blocked: Cannot approve invoice with unresolved blocking errors ({issues_list}). "
            f"Please correct the data or resolve the issues first."
        )
        return redirect('invoices:invoice_review', invoice_id=invoice.id)

    invoice.approval_status = 'APPROVED'
    invoice.approved_by = request.user
    invoice.approved_at = timezone.now()
    invoice.save(update_fields=['approval_status', 'approved_by', 'approved_at'])

    doc.status = 'APPROVED'
    doc.save(update_fields=['status'])

    AuditService.log(
        action='INVOICE_APPROVED',
        description=f"Invoice #{invoice.invoice_number} approved for accounting export by {request.user.get_full_name() or request.user.username}",
        invoice=invoice,
        user=request.user
    )

    messages.success(request, f"Invoice #{invoice.invoice_number} is now Approved and ready to Export.")
    return redirect('invoices:invoice_review', invoice_id=invoice.id)


@login_required
@require_http_methods(["POST"])
def invoice_reject_view(request, invoice_id):
    """Rejects an invoice with mandatory rejection notes."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    doc = invoice.document
    reason = request.POST.get('rejection_reason', 'Rejected during human review.')

    invoice.approval_status = 'REJECTED'
    invoice.notes = f"{invoice.notes}\n[REJECTION REASON]: {reason}".strip()
    invoice.save(update_fields=['approval_status', 'notes'])

    doc.status = 'REJECTED'
    doc.save(update_fields=['status'])

    AuditService.log(
        action='INVOICE_REJECTED',
        description=f"Invoice #{invoice.invoice_number} rejected: {reason}",
        invoice=invoice,
        user=request.user,
        details={'reason': reason}
    )

    messages.warning(request, f"Invoice #{invoice.invoice_number} has been rejected.")
    return redirect('invoices:invoice_review', invoice_id=invoice.id)


@login_required
@require_http_methods(["POST"])
def invoice_export_view(request, invoice_id):
    """Exports approved invoice to simulated accounting system."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    adapter = get_accounting_adapter()

    result = adapter.export_invoice(invoice, user=request.user)
    if result.success:
        messages.success(
            request, 
            f"🎉 Successfully exported to Accounting! Created Draft Bill Reference: {result.external_bill_id}"
        )
    else:
        messages.error(request, f"Export failed: {result.error or result.message}")

    return redirect('invoices:invoice_review', invoice_id=invoice.id)
