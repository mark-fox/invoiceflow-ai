from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExceptionType, InvoiceStatus, PurchaseOrderStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VendorOut(ORMModel):
    id: int
    name: str
    vendor_code: str


class PurchaseOrderOut(ORMModel):
    id: int
    po_number: str
    vendor_id: int
    total_amount: Decimal
    status: PurchaseOrderStatus
    created_at: datetime
    vendor: VendorOut


class InvoiceListItem(ORMModel):
    id: int
    invoice_number: str | None
    vendor_name: str | None
    total_amount: Decimal | None
    status: InvoiceStatus
    created_at: datetime


class InvoiceExceptionOut(ORMModel):
    id: int
    exception_type: ExceptionType
    description: str
    expected_value: str | None
    actual_value: str | None
    created_at: datetime


class AuditEventOut(ORMModel):
    id: int
    event_type: str
    message: str
    metadata: dict[str, Any] | None = Field(validation_alias="event_metadata")
    created_at: datetime


class InvoiceDetail(InvoiceListItem):
    po_number: str | None
    invoice_date: date | None
    extraction_confidence: Decimal | None
    updated_at: datetime
    purchase_order: PurchaseOrderOut | None = None
    exceptions: list[InvoiceExceptionOut]
    audit_events: list[AuditEventOut]


class DashboardSummary(BaseModel):
    total_invoices: int
    automatically_cleared: int
    needs_review: int
    approved: int
    rejected: int
    failed: int
    recent_invoices: list[InvoiceListItem]
