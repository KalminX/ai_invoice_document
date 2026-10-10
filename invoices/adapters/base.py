from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ExportResult:
    """Standardized result returned by accounting adapters."""
    success: bool
    external_bill_id: Optional[str] = None
    status: str = "DRAFT"
    message: str = ""
    request_payload: Dict[str, Any] = None
    response_payload: Dict[str, Any] = None
    error: Optional[str] = None


class AccountingAdapter(ABC):
    """Abstract interface for accounting integrations (Mock, Xero, QuickBooks, etc.)."""

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Unique identifier name of this adapter."""
        pass

    @abstractmethod
    def export_invoice(self, invoice, user=None) -> ExportResult:
        """
        Exports an approved invoice as a draft bill in the accounting system.
        Must enforce approval requirements, idempotency, and return an ExportResult.
        """
        pass

    @abstractmethod
    def get_bill_status(self, external_id: str) -> Dict[str, Any]:
        """Fetches status of an exported bill in the external ledger."""
        pass
