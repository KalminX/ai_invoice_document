import logging
import datetime
from decimal import Decimal
from typing import List
from django.utils import timezone
from ..models import Document, Invoice, InvoiceLineItem, ValidationIssue, Supplier

logger = logging.getLogger('invoices')


class ValidationService:
    """
    Independent Financial Validation and Integrity Verification Service.
    Applies strict deterministic business and financial calculation rules to
    detect errors, anomalies, and duplicates before human review or accounting export.
    """

    @classmethod
    def validate_invoice(cls, invoice: Invoice) -> List[ValidationIssue]:
        """
        Executes all validation checks on an invoice, persists ValidationIssue records,
        and updates the document/invoice validation status.
        """
        document = invoice.document
        
        # Clear existing un-resolved automated validation issues to re-evaluate
        ValidationIssue.objects.filter(invoice=invoice, is_resolved=False).delete()
        
        issues: List[ValidationIssue] = []

        # 1. Exact File Hash Duplicate Check
        hash_duplicates = Document.objects.filter(
            file_hash=document.file_hash
        ).exclude(id=document.id)
        
        if hash_duplicates.exists():
            dup_doc = hash_duplicates.first()
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='DUPLICATE_HASH',
                severity='ERROR',
                field_name='file_hash',
                message=(
                    f"Exact duplicate file detected! Identical SHA-256 hash matching document "
                    f"'{dup_doc.original_filename}' (Uploaded on {dup_doc.created_at.strftime('%Y-%m-%d %H:%M')})."
                ),
                is_blocking=True
            ))

        # 2. Supplier + Invoice Number Duplicate Check
        if invoice.invoice_number and invoice.supplier_name_raw:
            existing_invoices = Invoice.objects.filter(
                invoice_number__iexact=invoice.invoice_number.strip()
            ).exclude(id=invoice.id)
            
            # Match either by foreign key supplier or normalized string
            for ex_inv in existing_invoices:
                same_vendor = False
                if invoice.supplier and ex_inv.supplier and invoice.supplier == ex_inv.supplier:
                    same_vendor = True
                elif Supplier.normalize_supplier_name(invoice.supplier_name_raw) == Supplier.normalize_supplier_name(ex_inv.supplier_name_raw):
                    same_vendor = True
                
                if same_vendor:
                    invoice.is_duplicate = True
                    invoice.duplicate_of = ex_inv
                    issues.append(ValidationIssue(
                        document=document,
                        invoice=invoice,
                        issue_type='DUPLICATE_NUMBER',
                        severity='ERROR',
                        field_name='invoice_number',
                        message=(
                            f"Duplicate invoice detected: Invoice #{invoice.invoice_number} from "
                            f"'{invoice.supplier_name_raw}' already exists (Status: {ex_inv.get_approval_status_display()})."
                        ),
                        is_blocking=True
                    ))
                    break

        # 3. Required Fields Validation
        if not invoice.supplier_name_raw or not invoice.supplier_name_raw.strip():
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='MISSING_FIELD',
                severity='ERROR',
                field_name='supplier_name',
                message="Supplier / Vendor name is missing or could not be detected.",
                is_blocking=True
            ))

        if not invoice.invoice_number or not invoice.invoice_number.strip():
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='MISSING_FIELD',
                severity='ERROR',
                field_name='invoice_number',
                message="Invoice Number / Reference is missing or empty.",
                is_blocking=True
            ))

        if not invoice.invoice_date:
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='MISSING_FIELD',
                severity='ERROR',
                field_name='invoice_date',
                message="Invoice Issue Date is missing.",
                is_blocking=True
            ))

        if invoice.total_amount <= Decimal("0.00"):
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='MISSING_FIELD',
                severity='ERROR',
                field_name='total_amount',
                message="Total amount must be greater than zero.",
                is_blocking=True
            ))

        # 4. Independent Financial Arithmetic Verification (Using Python Decimal)
        expected_total = invoice.subtotal + invoice.tax_amount
        invoice.calculated_total = expected_total
        
        # Check Subtotal + Tax == Total
        if abs(invoice.total_amount - expected_total) > Decimal("0.01"):
            invoice.is_math_valid = False
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='ARITHMETIC_MISMATCH',
                severity='ERROR',
                field_name='total_amount',
                message=(
                    f"Financial calculation mismatch: Subtotal ({invoice.currency} {invoice.subtotal}) + "
                    f"Tax ({invoice.currency} {invoice.tax_amount}) = {invoice.currency} {expected_total}, "
                    f"but extracted Total is {invoice.currency} {invoice.total_amount}."
                ),
                is_blocking=True
            ))
        else:
            invoice.is_math_valid = True

        # 5. Line Items Sum Check & Line Item Arithmetic
        line_items = list(invoice.line_items.all())
        if line_items:
            lines_sum = sum(item.total_amount for item in line_items)
            
            # If subtotal is present, check lines_sum vs subtotal; else vs total
            target_sum = invoice.subtotal if invoice.subtotal > Decimal("0.00") else invoice.total_amount
            if abs(lines_sum - target_sum) > Decimal("0.05"):
                issues.append(ValidationIssue(
                    document=document,
                    invoice=invoice,
                    issue_type='LINE_ITEMS_MISMATCH',
                    severity='WARNING',
                    field_name='line_items',
                    message=(
                        f"Line items total sum ({invoice.currency} {lines_sum}) differs from "
                        f"stated net subtotal ({invoice.currency} {target_sum})."
                    ),
                    is_blocking=False
                ))

            # Individual line item arithmetic: qty * unit_price == total
            for item in line_items:
                calc_line_total = round(item.quantity * item.unit_price, 2)
                if abs(item.total_amount - calc_line_total) > Decimal("0.02") and item.unit_price > Decimal("0.00"):
                    issues.append(ValidationIssue(
                        document=document,
                        invoice=invoice,
                        issue_type='LINE_CALCULATION_MISMATCH',
                        severity='WARNING',
                        field_name=f'line_item_{item.line_number}',
                        message=(
                            f"Line {item.line_number} arithmetic anomaly: {item.quantity} x "
                            f"{item.unit_price} = {calc_line_total}, but line total is {item.total_amount}."
                        ),
                        is_blocking=False
                    ))

        # 6. Date Sanity Checks
        today = datetime.date.today()
        if invoice.invoice_date and invoice.invoice_date > (today + datetime.timedelta(days=30)):
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='DATE_ANOMALY',
                severity='WARNING',
                field_name='invoice_date',
                message=f"Invoice date ({invoice.invoice_date}) is significantly in the future.",
                is_blocking=False
            ))

        if invoice.invoice_date and invoice.due_date and invoice.due_date < invoice.invoice_date:
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='DATE_ANOMALY',
                severity='WARNING',
                field_name='due_date',
                message=f"Payment due date ({invoice.due_date}) precedes invoice date ({invoice.invoice_date}).",
                is_blocking=False
            ))

        # 7. Supplier Matching & Verification
        if invoice.supplier_name_raw:
            norm_name = Supplier.normalize_supplier_name(invoice.supplier_name_raw)
            matched_supplier = Supplier.objects.filter(normalized_name=norm_name).first()
            
            if not matched_supplier:
                # Try contains match
                matched_supplier = Supplier.objects.filter(normalized_name__icontains=norm_name).first()
            
            if matched_supplier:
                invoice.supplier = matched_supplier
                invoice.is_unknown_supplier = False
            else:
                invoice.supplier = None
                invoice.is_unknown_supplier = True
                issues.append(ValidationIssue(
                    document=document,
                    invoice=invoice,
                    issue_type='UNKNOWN_SUPPLIER',
                    severity='WARNING',
                    field_name='supplier',
                    message=f"Supplier '{invoice.supplier_name_raw}' is not recognized in approved supplier registry.",
                    is_blocking=False
                ))

        # 8. AI Extraction Confidence Check
        if document.confidence_score is not None and document.confidence_score < 0.80:
            issues.append(ValidationIssue(
                document=document,
                invoice=invoice,
                issue_type='LOW_CONFIDENCE',
                severity='WARNING',
                field_name='confidence_score',
                message=(
                    f"Low AI extraction confidence ({int(document.confidence_score * 100)}%). "
                    f"Careful manual verification of all fields is strongly recommended."
                ),
                is_blocking=False
            ))

        # Save all generated validation issues
        if issues:
            ValidationIssue.objects.bulk_create(issues)

        # Update Invoice and Document state
        blocking_count = sum(1 for issue in issues if issue.is_blocking)
        invoice.has_blocking_issues = (blocking_count > 0)
        invoice.save()

        # Update Document status if still in processing/review stages
        if document.status in ['UPLOADED', 'QUEUED', 'PROCESSING', 'READY_FOR_REVIEW', 'FLAGGED_ISSUES']:
            if blocking_count > 0 or len(issues) > 0:
                document.status = 'FLAGGED_ISSUES'
            else:
                document.status = 'READY_FOR_REVIEW'
            document.save(update_fields=['status'])

        return issues
