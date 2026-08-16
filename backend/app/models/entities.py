from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ExceptionType, InvoiceStatus, PurchaseOrderStatus


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    vendor_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[PurchaseOrderStatus] = mapped_column(Enum(PurchaseOrderStatus, name="purchase_order_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    vendor: Mapped[Vendor] = relationship(back_populates="purchase_orders")


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True)
    vendor_name: Mapped[str | None] = mapped_column(String(200), index=True)
    po_number: Mapped[str | None] = mapped_column(String(50), index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    file_path: Mapped[str] = mapped_column(String(500))
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus, name="invoice_status"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    exceptions: Mapped[list["InvoiceException"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceException(Base):
    __tablename__ = "invoice_exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    exception_type: Mapped[ExceptionType] = mapped_column(Enum(ExceptionType, name="exception_type"))
    description: Mapped[str] = mapped_column(Text)
    expected_value: Mapped[str | None] = mapped_column(String(255))
    actual_value: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    invoice: Mapped[Invoice] = relationship(back_populates="exceptions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    message: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    invoice: Mapped[Invoice] = relationship(back_populates="audit_events")

