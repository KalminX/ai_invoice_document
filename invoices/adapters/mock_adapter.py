import uuid
import time
import random
import logging
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from .base import AccountingAdapter, ExportResult
from ..models import Invoice, AccountingExport
from ..services.audit_service import AuditService

logger = logging.getLogger('invoices')


class MockAccountingAdapter(AccountingAdapter):
    """
    High-fidelity Mock Accounting System Adapter.
    Simulates enterprise accounting systems (e.g. Xero Draft Bills, QuickBooks Payables):
    - Strictly checks that invoices are human-approved
    - Enforces idempotency to prevent duplicate bill creation
    - Constructs realistic accounting JSON payload
    - Simulates bill generation and returns simulated external ID
    - Records attempts and audit trail entries
    """

    @property
    def adapter_name(self) -> str:
        return "mock"

    def export_invoice(self, invoice: Invoice, user=None) -> ExportResult:
        # Step 1: Pre-condition Validation (Strict Approval Requirement)
        if invoice.approval_status != 'APPROVED' and invoice.approval_status != 'EXPORTED':
            error_msg = f"Cannot export invoice #{invoice.invoice_number}: Approval status is '{invoice.get_approval_status_display()}', but 'Approved' is strictly required."
            logger.warning(error_msg)
            AuditService.log(
                action='EXPORT_FAILED',
                description=error_msg,
                invoice=invoice,
                user=user,
                details={'reason': 'UNAPPROVED_INVOICE'}
            )
            return ExportResult(
                success=False,
                error=error_msg,
                message="Export blocked: Invoice must be explicitly approved by a human reviewer first."
            )

        # Step 2: Idempotency & Duplicate Export Prevention
        idempotency_key = f"MOCK-INV-{invoice.id}-{invoice.invoice_number}-{invoice.document.file_hash[:12]}"
        existing_export = AccountingExport.objects.filter(invoice=invoice).first()

        if existing_export and existing_export.status == 'SUCCESS':
            logger.info(f"Idempotency hit: Invoice #{invoice.invoice_number} already exported as {existing_export.external_bill_id}")
            return ExportResult(
                success=True,
                external_bill_id=existing_export.external_bill_id,
                status="ALREADY_EXPORTED",
                message=f"Invoice has already been successfully exported to Draft Bill {existing_export.external_bill_id}.",
                request_payload=existing_export.request_payload,
                response_payload=existing_export.response_payload
            )

        AuditService.log(
            action='EXPORT_ATTEMPT',
            description=f"Initiating mock accounting draft bill export for Invoice #{invoice.invoice_number}",
            invoice=invoice,
            user=user
        )

        # Step 3: Construct Simulated Accounting Payload (Draft Bill)
        line_items_payload = []
        for line in invoice.line_items.all():
            line_items_payload.append({
                "line_number": line.line_number,
                "description": line.description,
                "quantity": float(line.quantity),
                "unit_amount": float(line.unit_price),
                "line_amount": float(line.total_amount),
                "account_code": line.account_code.code if line.account_code else "2000-UNALLOCATED",
                "account_name": line.account_code.name if line.account_code else "Unallocated Expenses",
                "tax_type": "OUTPUT_TAX" if invoice.tax_amount > 0 else "NONE"
            })

        request_payload = {
            "type": "ACCPAY",  # Accounts Payable / Bill
            "contact": {
                "name": invoice.supplier.name if invoice.supplier else invoice.supplier_name_raw,
                "tax_number": invoice.supplier.tax_id if invoice.supplier else "",
            },
            "invoice_number": invoice.invoice_number,
            "date": invoice.invoice_date.isoformat() if invoice.invoice_date else timezone.now().date().isoformat(),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "currency_code": invoice.currency,
            "subtotal": float(invoice.subtotal),
            "total_tax": float(invoice.tax_amount),
            "total": float(invoice.total_amount),
            "status": "DRAFT",
            "line_items": line_items_payload,
            "idempotency_key": idempotency_key,
        }

        # Step 4: Simulate Network / Accounting Platform Processing
        failure_rate = getattr(settings, 'MOCK_ACCOUNTING_FAILURE_RATE', 0.0)
        if failure_rate > 0.0 and random.random() < failure_rate:
            error_msg = "Simulated Mock Accounting Network Error: Connection timeout (504 Gateway Timeout)"
            if not existing_export:
                AccountingExport.objects.create(
                    invoice=invoice,
                    adapter_name=self.adapter_name,
                    status='FAILED',
                    idempotency_key=idempotency_key,
                    request_payload=request_payload,
                    error_message=error_msg,
                    exported_by=user,
                    attempt_count=1
                )
            else:
                existing_export.attempt_count += 1
                existing_export.error_message = error_msg
                existing_export.status = 'FAILED'
                existing_export.save()

            AuditService.log(
                action='EXPORT_FAILED',
                description=f"Export failed for Invoice #{invoice.invoice_number}: {error_msg}",
                invoice=invoice,
                user=user,
                details={'error': error_msg}
            )
            return ExportResult(
                success=False,
                error=error_msg,
                request_payload=request_payload
            )

        # Generate unique external Draft Bill reference
        external_bill_id = f"MOCK-BILL-{uuid.uuid4().hex[:8].upper()}"
        response_payload = {
            "bill_id": external_bill_id,
            "status": "DRAFT",
            "created_at": timezone.now().isoformat(),
            "external_reference": f"EXT-REF-{invoice.id}",
            "reconciliation_status": "UNPAID",
            "message": "Draft bill created successfully in Simulated Accounting Ledger."
        }

        # Save Accounting Export record
        if not existing_export:
            export_record = AccountingExport.objects.create(
                invoice=invoice,
                adapter_name=self.adapter_name,
                external_bill_id=external_bill_id,
                status='SUCCESS',
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                response_payload=response_payload,
                exported_by=user,
                exported_at=timezone.now(),
                attempt_count=1
            )
        else:
            existing_export.external_bill_id = external_bill_id
            existing_export.status = 'SUCCESS'
            existing_export.request_payload = request_payload
            existing_export.response_payload = response_payload
            existing_export.error_message = ''
            existing_export.exported_by = user
            existing_export.exported_at = timezone.now()
            existing_export.attempt_count += 1
            existing_export.save()

        # Update Document and Invoice status
        invoice.approval_status = 'EXPORTED'
        invoice.save(update_fields=['approval_status'])
        
        doc = invoice.document
        doc.status = 'EXPORTED'
        doc.save(update_fields=['status'])

        AuditService.log(
            action='EXPORT_SUCCESS',
            description=f"Successfully exported Invoice #{invoice.invoice_number} to simulated Draft Bill {external_bill_id}",
            invoice=invoice,
            document=doc,
            user=user,
            details={
                'external_bill_id': external_bill_id,
                'adapter': self.adapter_name,
                'lines_count': len(line_items_payload),
                'total': float(invoice.total_amount)
            }
        )

        return ExportResult(
            success=True,
            external_bill_id=external_bill_id,
            status="DRAFT",
            message=f"Draft Bill {external_bill_id} created successfully.",
            request_payload=request_payload,
            response_payload=response_payload
        )

    def get_bill_status(self, external_id: str):
        return {
            "bill_id": external_id,
            "status": "DRAFT",
            "ledger": "Simulated Enterprise Ledger",
            "is_paid": False
        }
