import uuid
import hashlib
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AccountCode(models.Model):
    """Chart of accounts entry for general ledger coding."""
    CATEGORY_CHOICES = [
        ('EXPENSE', 'Operating Expense'),
        ('COGS', 'Cost of Goods Sold'),
        ('ASSET', 'Asset / Equipment'),
        ('LIABILITY', 'Liability'),
        ('OTHER', 'Other Expense'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='EXPENSE')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Supplier(models.Model):
    """Approved or recognized supplier / vendor."""
    name = models.CharField(max_length=255, unique=True)
    normalized_name = models.CharField(max_length=255, db_index=True)
    tax_id = models.CharField(max_length=50, blank=True, verbose_name="Tax/VAT ID")
    default_account_code = models.ForeignKey(
        AccountCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='suppliers'
    )
    contact_email = models.EmailField(blank=True)
    default_currency = models.CharField(max_length=10, default='USD')
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        self.normalized_name = self.normalize_supplier_name(self.name)
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_supplier_name(name: str) -> str:
        if not name:
            return ""
        # Lowercase, remove punctuation and standard legal suffixes
        import re
        norm = name.lower().strip()
        norm = re.sub(r'[\.,\-_\(\)]', ' ', norm)
        norm = re.sub(r'\b(inc|llc|ltd|corp|corporation|gmbh|co|pty|limited)\b', '', norm)
        return ' '.join(norm.split())

    def __str__(self):
        return self.name


class Document(models.Model):
    """Uploaded physical or digital invoice document."""
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('QUEUED', 'Queued for Extraction'),
        ('PROCESSING', 'Processing AI Extraction'),
        ('READY_FOR_REVIEW', 'Ready for Review'),
        ('FLAGGED_ISSUES', 'Validation Issues Flagged'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPORTED', 'Exported to Accounting'),
        ('FAILED', 'Extraction Failed'),
    ]

    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF Document'),
        ('png', 'PNG Image'),
        ('jpeg', 'JPEG Image'),
        ('jpg', 'JPG Image'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='invoices/%Y/%m/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_hash = models.CharField(max_length=64, db_index=True, help_text="SHA-256 hash for exact duplicate detection")
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='UPLOADED', db_index=True)
    extraction_mode_used = models.CharField(max_length=20, default='mock')  # 'gemini' or 'mock'
    confidence_score = models.FloatField(null=True, blank=True, help_text="AI extraction confidence score (0.0 - 1.0)")
    raw_extraction_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_documents')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_filename} ({self.get_status_display()})"

    @staticmethod
    def calculate_file_hash(file_obj) -> str:
        """Calculate SHA-256 hash of a file object."""
        hasher = hashlib.sha256()
        file_obj.seek(0)
        for chunk in file_obj.chunks(4096) if hasattr(file_obj, 'chunks') else iter(lambda: file_obj.read(4096), b''):
            hasher.update(chunk)
        file_obj.seek(0)
        return hasher.hexdigest()


class Invoice(models.Model):
    """Structured invoice extracted from a document."""
    APPROVAL_STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPORTED', 'Exported'),
    ]

    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='invoice')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    supplier_name_raw = models.CharField(max_length=255, blank=True, help_text="Extracted raw vendor name")
    invoice_number = models.CharField(max_length=100, blank=True, db_index=True)
    invoice_date = models.DateField(null=True, blank=True, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    calculated_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Subtotal + Tax")
    
    is_math_valid = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='duplicates')
    is_unknown_supplier = models.BooleanField(default=False)
    has_blocking_issues = models.BooleanField(default=False)
    
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING', db_index=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_invoices')
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice {self.invoice_number or 'UNNUMBERED'} - {self.supplier_name_raw or 'Unknown Supplier'}"

    @property
    def can_approve(self) -> bool:
        """Invoice can only be approved if it has no active unresolved blocking validation issues."""
        unresolved_blocking = self.validation_issues.filter(is_blocking=True, is_resolved=False).exists()
        return not unresolved_blocking and self.approval_status != 'APPROVED' and self.approval_status != 'EXPORTED'

    @property
    def can_export(self) -> bool:
        """Invoice can only be exported if approved and not yet exported."""
        return self.approval_status == 'APPROVED' and not hasattr(self, 'accounting_export')

    @property
    def unresolved_issues_count(self) -> int:
        return self.validation_issues.filter(is_resolved=False).count()

    @property
    def blocking_issues_count(self) -> int:
        return self.validation_issues.filter(is_blocking=True, is_resolved=False).count()


class InvoiceLineItem(models.Model):
    """Line item itemized within an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    line_number = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    account_code = models.ForeignKey(
        AccountCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='line_items'
    )
    suggested_account_code = models.ForeignKey(
        AccountCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='suggested_line_items'
    )
    suggestion_confidence = models.FloatField(null=True, blank=True)
    suggestion_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['line_number', 'id']

    def __str__(self):
        return f"Line {self.line_number}: {self.description[:40]} ({self.total_amount})"


class ValidationIssue(models.Model):
    """Automated independent validation check failure or anomaly."""
    ISSUE_TYPE_CHOICES = [
        ('ARITHMETIC_MISMATCH', 'Arithmetic Mismatch (Subtotal + Tax != Total)'),
        ('LINE_ITEMS_MISMATCH', 'Line Items Sum Mismatch'),
        ('LINE_CALCULATION_MISMATCH', 'Line Item Quantity x Price Mismatch'),
        ('DUPLICATE_HASH', 'Exact Duplicate Document (Hash Match)'),
        ('DUPLICATE_NUMBER', 'Duplicate Invoice (Supplier + Invoice # Match)'),
        ('UNKNOWN_SUPPLIER', 'Unknown / Unrecognized Supplier'),
        ('MISSING_FIELD', 'Missing Required Field'),
        ('LOW_CONFIDENCE', 'Low AI Extraction Confidence'),
        ('DATE_ANOMALY', 'Date Anomaly (Future Date or Due Date Before Invoice Date)'),
        ('EXTRACTION_FAILED', 'AI Extraction Failed'),
        ('UNASSIGNED_ACCOUNT_CODE', 'Line item missing General Ledger Account Code'),
    ]

    SEVERITY_CHOICES = [
        ('ERROR', 'Error (Blocking)'),
        ('WARNING', 'Warning (Review Recommended)'),
        ('INFO', 'Information'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='validation_issues')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name='validation_issues')
    issue_type = models.CharField(max_length=35, choices=ISSUE_TYPE_CHOICES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='ERROR')
    field_name = models.CharField(max_length=100, blank=True)
    message = models.TextField()
    is_blocking = models.BooleanField(default=True)
    
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_issues')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', '-created_at']

    def __str__(self):
        status = "RESOLVED" if self.is_resolved else "UNRESOLVED"
        return f"[{self.severity}] {self.get_issue_type_display()} - {status}"


class AuditLog(models.Model):
    """Immutable audit trail of actions taken on documents and invoices."""
    ACTION_CHOICES = [
        ('UPLOAD', 'Document Uploaded'),
        ('EXTRACTION_START', 'Extraction Started'),
        ('EXTRACTION_SUCCESS', 'Extraction Completed'),
        ('EXTRACTION_FAILED', 'Extraction Failed'),
        ('VALIDATION_RUN', 'Validation Performed'),
        ('FIELD_UPDATED', 'Invoice Field Updated'),
        ('LINE_ITEM_ADDED', 'Line Item Added'),
        ('LINE_ITEM_EDITED', 'Line Item Edited'),
        ('LINE_ITEM_DELETED', 'Line Item Deleted'),
        ('ISSUE_RESOLVED', 'Validation Issue Resolved'),
        ('INVOICE_APPROVED', 'Invoice Approved'),
        ('INVOICE_REJECTED', 'Invoice Rejected'),
        ('EXPORT_ATTEMPT', 'Accounting Export Attempted'),
        ('EXPORT_SUCCESS', 'Accounting Export Succeeded'),
        ('EXPORT_FAILED', 'Accounting Export Failed'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {user_str}: {self.get_action_display()}"


class ProcessingJob(models.Model):
    """Database-backed background queue for asynchronous processing."""
    JOB_TYPE_CHOICES = [
        ('EXTRACT_AND_VALIDATE', 'Extract and Validate Invoice'),
        ('EXPORT_ACCOUNTING', 'Export to Accounting System'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='processing_jobs')
    job_type = models.CharField(max_length=30, choices=JOB_TYPE_CHOICES, default='EXTRACT_AND_VALIDATE')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    error_log = models.TextField(blank=True)
    
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at', 'created_at']

    def __str__(self):
        return f"Job #{self.id} {self.job_type} ({self.status}) for {self.document.original_filename}"


class AccountingExport(models.Model):
    """Record of synchronized draft bill in the accounting platform."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Exported Successfully'),
        ('FAILED', 'Export Failed'),
    ]

    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='accounting_export')
    adapter_name = models.CharField(max_length=50, default='mock')
    external_bill_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    idempotency_key = models.CharField(max_length=128, unique=True, db_index=True)
    
    request_payload = models.JSONField(default=dict)
    response_payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=1)
    
    exported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Export for Invoice #{self.invoice.invoice_number} -> {self.external_bill_id} ({self.status})"
