import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from invoices.models import AccountingExport, Invoice
from invoices.adapters.factory import get_accounting_adapter


@login_required
def export_ledger_view(request):
    """View of all draft bills exported to the general ledger accounting platform."""
    exports = AccountingExport.objects.select_related(
        'invoice', 'invoice__supplier', 'invoice__document', 'exported_by'
    ).order_by('-created_at')

    total_exported_val = Invoice.objects.filter(
        accounting_export__status='SUCCESS'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    approved_pending_export = Invoice.objects.filter(
        approval_status='APPROVED'
    ).exclude(accounting_export__status='SUCCESS')

    context = {
        'exports': exports,
        'total_exported_val': total_exported_val,
        'approved_pending_count': approved_pending_export.count(),
        'approved_pending_list': approved_pending_export[:5],
    }
    return render(request, 'invoices/accounting/export_ledger.html', context)


@login_required
def batch_export_view(request):
    """Batch export all approved invoices."""
    if request.method == "POST":
        approved_invoices = Invoice.objects.filter(
            approval_status='APPROVED'
        ).exclude(accounting_export__status='SUCCESS')

        adapter = get_accounting_adapter()
        success_count = 0
        error_count = 0

        for inv in approved_invoices:
            res = adapter.export_invoice(inv, user=request.user)
            if res.success:
                success_count += 1
            else:
                error_count += 1

        if success_count > 0:
            messages.success(request, f"Successfully exported {success_count} approved invoice(s) to Accounting Ledger.")
        if error_count > 0:
            messages.error(request, f"Failed to export {error_count} invoice(s).")

    return redirect('invoices:export_ledger')


@login_required
def retry_export_view(request, export_id):
    """Retries a failed accounting export."""
    export_rec = get_object_or_404(AccountingExport, id=export_id)
    adapter = get_accounting_adapter()
    
    result = adapter.export_invoice(export_rec.invoice, user=request.user)
    if result.success:
        messages.success(request, f"Retry succeeded! Draft Bill ID: {result.external_bill_id}")
    else:
        messages.error(request, f"Retry failed: {result.error}")

    return redirect('invoices:export_ledger')
