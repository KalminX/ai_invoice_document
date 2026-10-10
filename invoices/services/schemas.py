from decimal import Decimal
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class LineItemSchema(BaseModel):
    """Pydantic schema for individual extracted invoice line items."""
    description: str = Field(description="Description of the item or service rendered")
    quantity: Decimal = Field(default=Decimal("1.00"), description="Quantity of units")
    unit_price: Decimal = Field(default=Decimal("0.00"), description="Price per single unit")
    total_amount: Decimal = Field(default=Decimal("0.00"), description="Total line amount (quantity * unit_price)")
    account_code: Optional[str] = Field(default=None, description="Suggested GL account code if identifiable")

    @field_validator('quantity', 'unit_price', 'total_amount', mode='before')
    @classmethod
    def parse_decimals(cls, v):
        if v is None or v == "":
            return Decimal("0.00")
        if isinstance(v, (int, float, str)):
            # Clean currency symbols or commas
            if isinstance(v, str):
                v = v.replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
                if not v:
                    return Decimal("0.00")
            try:
                return round(Decimal(str(v)), 2)
            except Exception:
                return Decimal("0.00")
        return v


class InvoiceExtractionSchema(BaseModel):
    """Strict Pydantic schema for AI invoice data extraction."""
    supplier_name: Optional[str] = Field(default=None, description="Name of the vendor/supplier issuing the invoice")
    tax_id: Optional[str] = Field(default=None, description="Tax ID / VAT registration number of supplier")
    invoice_number: Optional[str] = Field(default=None, description="Invoice reference or identification number")
    invoice_date: Optional[date] = Field(default=None, description="Date the invoice was issued (YYYY-MM-DD)")
    due_date: Optional[date] = Field(default=None, description="Payment due date (YYYY-MM-DD)")
    currency: str = Field(default="USD", description="Three-letter ISO currency code (USD, EUR, GBP, AUD, CAD, etc.)")
    subtotal: Decimal = Field(default=Decimal("0.00"), description="Net total amount before tax")
    tax_amount: Decimal = Field(default=Decimal("0.00"), description="Total tax / VAT / GST amount")
    total_amount: Decimal = Field(default=Decimal("0.00"), description="Gross total invoice amount")
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0, description="Confidence rating of the AI extraction between 0.0 and 1.0")
    line_items: List[LineItemSchema] = Field(default_factory=list, description="List of itemized invoice lines")
    notes: Optional[str] = Field(default=None, description="Payment terms or notes found on the invoice")

    @field_validator('subtotal', 'tax_amount', 'total_amount', mode='before')
    @classmethod
    def parse_currency_decimals(cls, v):
        if v is None or v == "":
            return Decimal("0.00")
        if isinstance(v, (int, float, str)):
            if isinstance(v, str):
                v = v.replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
                if not v:
                    return Decimal("0.00")
            try:
                return round(Decimal(str(v)), 2)
            except Exception:
                return Decimal("0.00")
        return v

    @field_validator('currency', mode='before')
    @classmethod
    def normalize_currency(cls, v):
        if not v or not isinstance(v, str):
            return "USD"
        v = v.strip().upper()
        symbol_map = {'$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY'}
        return symbol_map.get(v, v[:3])
