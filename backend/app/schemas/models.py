from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class DuplicateCheckOut(BaseModel):
    is_duplicate: bool
    matching_invoice_id: int | None = None


class ProcessingDispatchOut(BaseModel):
    dispatched: bool
    invoice_id: int


class ProcessingExceptionIn(BaseModel):
    exception_type: ExceptionType
    description: str
    expected_value: str | None = None
    actual_value: str | None = None


class ProcessingResultIn(BaseModel):
    invoice_number: str | None
    vendor_name: str | None
    po_number: str | None
    invoice_date: date | None
    total_amount: Decimal | None
    extraction_confidence: Decimal | None = Field(ge=0, le=1)
    status: InvoiceStatus
    exceptions: list[ProcessingExceptionIn] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def validate_terminal_processing_status(
        cls, value: InvoiceStatus
    ) -> InvoiceStatus:
        allowed_statuses = {
            InvoiceStatus.CLEARED,
            InvoiceStatus.NEEDS_REVIEW,
            InvoiceStatus.FAILED,
        }
        if value not in allowed_statuses:
            raise ValueError(
                "Processing result status must be CLEARED, NEEDS_REVIEW, or FAILED."
            )
        return value


class DashboardSummary(BaseModel):
    total_invoices: int
    automatically_cleared: int
    needs_review: int
    approved: int
    rejected: int
    failed: int
    recent_invoices: list[InvoiceListItem]


class AutomationInvoiceCounts(BaseModel):
    total: int
    uploaded: int
    processing: int
    cleared: int
    needs_review: int
    failed: int
    approved: int
    rejected: int


class AutomationSummary(BaseModel):
    invoice_counts: AutomationInvoiceCounts
    exception_counts: dict[ExceptionType, int]


class RecentProcessingItem(BaseModel):
    invoice_id: int
    invoice_number: str | None
    vendor_name: str | None
    status: InvoiceStatus
    completed_at: datetime
    exception_count: int


class AutomationMetrics(BaseModel):
    completed_count: int
    auto_cleared_count: int
    needs_review_count: int
    failed_count: int
    auto_clear_rate: float
    review_rate: float
    failure_rate: float
    average_processing_seconds: float | None
