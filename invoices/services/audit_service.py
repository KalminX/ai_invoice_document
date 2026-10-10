import logging
from typing import Optional, Dict, Any
from django.contrib.auth.models import User
from ..models import AuditLog, Document, Invoice

logger = logging.getLogger('invoices')


class AuditService:
    """Centralized service for writing immutable audit trail entries."""

    @classmethod
    def log(
        cls,
        action: str,
        description: str,
        document: Optional[Document] = None,
        invoice: Optional[Invoice] = None,
        user: Optional[User] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Creates an audit log entry."""
        if not document and invoice:
            document = invoice.document
        if not invoice and document and hasattr(document, 'invoice'):
            invoice = document.invoice

        entry = AuditLog.objects.create(
            document=document,
            invoice=invoice,
            user=user,
            action=action,
            description=description,
            details=details or {},
            ip_address=ip_address
        )
        logger.info(f"AUDIT [{action}] {description} (User: {user or 'System'})")
        return entry
