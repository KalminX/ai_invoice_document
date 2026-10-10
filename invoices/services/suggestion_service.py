import re
from typing import Optional, Tuple
from django.db.models import Count
from ..models import AccountCode, Supplier, InvoiceLineItem, Invoice


class AccountCodingSuggestionService:
    """
    Intelligent Account Coding Suggestion Engine.
    Suggests General Ledger (GL) account codes based on:
    1. Supplier default account code
    2. Historical approved invoices from the same supplier
    3. Historical approved line item description keyword matching
    
    If evidence is insufficient, it explicitly returns (None, 0.0, reason)
    and strictly avoids hallucinating or guessing codes.
    """

    @classmethod
    def suggest_for_line_item(
        cls, 
        description: str, 
        supplier: Optional[Supplier] = None,
        extracted_supplier_name: Optional[str] = None
    ) -> Tuple[Optional[AccountCode], float, str]:
        """
        Returns (AccountCode or None, confidence_score, explanation_reason).
        """
        clean_desc = description.strip().lower() if description else ""

        # Step 1: Check Supplier's configured default account code
        if supplier and supplier.default_account_code and supplier.default_account_code.is_active:
            return (
                supplier.default_account_code,
                0.95,
                f"Configured default for approved supplier '{supplier.name}'"
            )

        # Step 2: Check historical approved line items from the exact same supplier
        if supplier:
            supplier_approved_items = InvoiceLineItem.objects.filter(
                invoice__supplier=supplier,
                invoice__approval_status__in=['APPROVED', 'EXPORTED'],
                account_code__isnull=False,
                account_code__is_active=True
            ).values('account_code').annotate(count=Count('account_code')).order_by('-count')

            if supplier_approved_items.exists():
                top_code_id = supplier_approved_items[0]['account_code']
                account = AccountCode.objects.filter(id=top_code_id, is_active=True).first()
                if account:
                    return (
                        account,
                        0.90,
                        f"Most frequent account ({account.code}) in approved invoices for {supplier.name}"
                    )

        # Step 3: Match description keywords against historical approved line items
        if clean_desc:
            tokens = [w for w in re.split(r'[\s,\.\-_/]+', clean_desc) if len(w) > 3]
            for token in tokens:
                matched_items = InvoiceLineItem.objects.filter(
                    description__icontains=token,
                    invoice__approval_status__in=['APPROVED', 'EXPORTED'],
                    account_code__isnull=False,
                    account_code__is_active=True
                ).values('account_code').annotate(count=Count('account_code')).order_by('-count')

                if matched_items.exists():
                    top_code_id = matched_items[0]['account_code']
                    account = AccountCode.objects.filter(id=top_code_id, is_active=True).first()
                    if account:
                        return (
                            account,
                            0.80,
                            f"Matched historical keyword '{token}' in approved line items ({account.code})"
                        )

        # Step 4: Fallback - Explicitly indicate no suggestion is available
        return (
            None,
            0.0,
            "No historical coding history available — manual account assignment required"
        )
