import logging
from typing import Dict, Any
from .base import AccountingAdapter, ExportResult
from ..models import Invoice

logger = logging.getLogger('invoices')


class XeroAccountingAdapter(AccountingAdapter):
    """
    Xero Accounting Integration Adapter.
    Ready for OAuth2 connection and Xero Invoices / Bills API.
    """

    @property
    def adapter_name(self) -> str:
        return "xero"

    def export_invoice(self, invoice: Invoice, user=None) -> ExportResult:
        # Check approval
        if invoice.approval_status != 'APPROVED':
            return ExportResult(
                success=False,
                error="Invoice must be approved before exporting to Xero.",
                message="Approval required."
            )

        logger.info(f"Xero adapter selected for Invoice #{invoice.invoice_number}. Ready for OAuth credentials.")
        return ExportResult(
            success=False,
            error="Xero credentials not configured. Please use Mock Adapter for demonstration.",
            message="Xero OAuth credentials required."
        )

    def get_bill_status(self, external_id: str) -> Dict[str, Any]:
        return {"status": "UNCONFIGURED", "message": "Xero adapter requires API credentials."}
