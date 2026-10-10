import logging
import traceback
from django.conf import settings
from django.utils import timezone
from ..models import Document, Invoice, InvoiceLineItem, ValidationIssue, Supplier
from .gemini_extractor import extract_with_gemini, GeminiExtractionError
from .mock_extractor import extract_with_mock
from .validation_service import ValidationService
from .suggestion_service import AccountCodingSuggestionService
from .audit_service import AuditService

logger = logging.getLogger('invoices')


class ExtractionService:
    """
    Core Extraction Orchestration Service.
    Coordinates document extraction (Gemini AI or Mock Engine), parses into models,
    executes account coding suggestions, triggers independent validation, and logs audit events.
    """

    @classmethod
    def process_document(cls, document: Document, user=None, force_mode: str = None) -> Invoice:
        """
        Executes extraction pipeline on a Document record.
        """
        document.status = 'PROCESSING'
        document.save(update_fields=['status'])
        
        AuditService.log(
            action='EXTRACTION_START',
            description=f"Starting extraction for '{document.original_filename}'",
            document=document,
            user=user
        )

        mode_to_use = force_mode or getattr(settings, 'EXTRACTION_MODE', 'auto')
        gemini_api_key = getattr(settings, 'GEMINI_API_KEY', '')

        extracted_schema = None
        mode_used = 'mock'
        
        try:
            if mode_to_use == 'gemini' or (mode_to_use == 'auto' and bool(gemini_api_key)):
                try:
                    logger.info(f"Attempting Gemini extraction for {document.original_filename}")
                    extracted_schema = extract_with_gemini(document.file.path, document.file_type)
                    mode_used = 'gemini'
                except Exception as e:
                    if mode_to_use == 'gemini':
                        raise
                    logger.warning(f"Gemini extraction failed, falling back to mock: {e}")
                    extracted_schema = extract_with_mock(document.file.path, document.original_filename)
                    mode_used = 'mock (fallback)'
            else:
                logger.info(f"Using Mock Extraction for {document.original_filename}")
                extracted_schema = extract_with_mock(document.file.path, document.original_filename)
                mode_used = 'mock'

            document.extraction_mode_used = mode_used
            document.confidence_score = extracted_schema.confidence_score
            document.raw_extraction_data = extracted_schema.model_dump(mode='json')
            document.save(update_fields=['extraction_mode_used', 'confidence_score', 'raw_extraction_data'])

            # Match initial Supplier if existing
            supplier = None
            if extracted_schema.supplier_name:
                norm_name = Supplier.normalize_supplier_name(extracted_schema.supplier_name)
                supplier = Supplier.objects.filter(normalized_name=norm_name).first()

            # Create or update Invoice model
            invoice, created = Invoice.objects.update_or_create(
                document=document,
                defaults={
                    'supplier': supplier,
                    'supplier_name_raw': extracted_schema.supplier_name or '',
                    'invoice_number': extracted_schema.invoice_number or '',
                    'invoice_date': extracted_schema.invoice_date,
                    'due_date': extracted_schema.due_date,
                    'currency': extracted_schema.currency or 'USD',
                    'subtotal': extracted_schema.subtotal,
                    'tax_amount': extracted_schema.tax_amount,
                    'total_amount': extracted_schema.total_amount,
                    'notes': extracted_schema.notes or '',
                    'approval_status': 'PENDING',
                }
            )

            # Recreate Line Items
            invoice.line_items.all().delete()
            for idx, item in enumerate(extracted_schema.line_items, start=1):
                # Suggest account code
                suggested_acc, conf, reason = AccountCodingSuggestionService.suggest_for_line_item(
                    description=item.description,
                    supplier=supplier,
                    extracted_supplier_name=extracted_schema.supplier_name
                )

                # If schema gave an account code and it exists, use it or fallback to suggestion
                actual_acc = None
                if item.account_code:
                    from ..models import AccountCode
                    actual_acc = AccountCode.objects.filter(code=item.account_code).first()
                if not actual_acc and suggested_acc:
                    actual_acc = suggested_acc

                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    line_number=idx,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_amount=item.total_amount,
                    account_code=actual_acc,
                    suggested_account_code=suggested_acc,
                    suggestion_confidence=conf if suggested_acc else None,
                    suggestion_reason=reason,
                )

            # Run Independent Validation
            issues = ValidationService.validate_invoice(invoice)

            AuditService.log(
                action='EXTRACTION_SUCCESS',
                description=(
                    f"Successfully extracted invoice #{invoice.invoice_number or 'N/A'} "
                    f"via {mode_used.upper()} engine. Found {len(issues)} validation issue(s)."
                ),
                document=document,
                invoice=invoice,
                user=user,
                details={
                    'mode': mode_used,
                    'confidence': document.confidence_score,
                    'line_items_count': len(extracted_schema.line_items),
                    'issues_count': len(issues),
                }
            )

            return invoice

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Extraction failed for document {document.id}: {e}\n{tb}")
            document.status = 'FAILED'
            document.error_message = str(e)
            document.save(update_fields=['status', 'error_message'])

            # Record Validation Issue for the extraction failure
            ValidationIssue.objects.create(
                document=document,
                issue_type='EXTRACTION_FAILED',
                severity='ERROR',
                field_name='file',
                message=f"Extraction failed: {str(e)}",
                is_blocking=True
            )

            AuditService.log(
                action='EXTRACTION_FAILED',
                description=f"Extraction failed: {str(e)}",
                document=document,
                user=user,
                details={'error': str(e), 'traceback': tb}
            )
            raise
