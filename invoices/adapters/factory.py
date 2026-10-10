from django.conf import settings
from .base import AccountingAdapter
from .mock_adapter import MockAccountingAdapter
from .xero_adapter import XeroAccountingAdapter


def get_accounting_adapter(adapter_name: str = None) -> AccountingAdapter:
    """Returns the configured accounting system adapter instance."""
    name = adapter_name or getattr(settings, 'DEFAULT_ACCOUNTING_ADAPTER', 'mock').lower()
    
    if name == 'xero':
        return XeroAccountingAdapter()
    return MockAccountingAdapter()
