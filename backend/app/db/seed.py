from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, ExceptionType, Invoice, InvoiceException, InvoiceStatus, PurchaseOrder, PurchaseOrderStatus, Vendor


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(func.count(Vendor.id))):
        return
    vendors = [
        Vendor(name="Northstar Office Supply", vendor_code="NOS-1042"),
        Vendor(name="Summit IT Solutions", vendor_code="SIT-2088"),
        Vendor(name="Harbor Facilities Group", vendor_code="HFG-3115"),
        Vendor(name="Brightline Creative", vendor_code="BLC-4071"),
        Vendor(name="Evergreen Logistics", vendor_code="EGL-5520"),
    ]
    db.add_all(vendors)
    db.flush()
    now = datetime.now(timezone.utc)
    pos = [
        PurchaseOrder(po_number="PO-2026-1048", vendor=vendors[0], total_amount=Decimal("4280.50"), status=PurchaseOrderStatus.OPEN, created_at=now-timedelta(days=30)),
        PurchaseOrder(po_number="PO-2026-1051", vendor=vendors[1], total_amount=Decimal("18640.00"), status=PurchaseOrderStatus.PARTIALLY_INVOICED, created_at=now-timedelta(days=24)),
        PurchaseOrder(po_number="PO-2026-1063", vendor=vendors[2], total_amount=Decimal("7950.00"), status=PurchaseOrderStatus.OPEN, created_at=now-timedelta(days=18)),
        PurchaseOrder(po_number="PO-2026-1070", vendor=vendors[3], total_amount=Decimal("3200.00"), status=PurchaseOrderStatus.CLOSED, created_at=now-timedelta(days=12)),
        PurchaseOrder(po_number="PO-2026-1074", vendor=vendors[4], total_amount=Decimal("12125.75"), status=PurchaseOrderStatus.OPEN, created_at=now-timedelta(days=7)),
    ]
    db.add_all(pos)
    samples = [
        ("INV-88412", vendors[0].name, pos[0].po_number, "4280.50", InvoiceStatus.CLEARED, Decimal("0.9820"), 2),
        ("SIT-77109", vendors[1].name, pos[1].po_number, "9450.00", InvoiceStatus.NEEDS_REVIEW, Decimal("0.8730"), 1),
        ("HF-23018", vendors[2].name, pos[2].po_number, "7950.00", InvoiceStatus.APPROVED, Decimal("0.9210"), 4),
        ("BC-5682", vendors[3].name, pos[3].po_number, "3200.00", InvoiceStatus.REJECTED, Decimal("0.8940"), 6),
        ("EGL-90155", vendors[4].name, pos[4].po_number, "12125.75", InvoiceStatus.FAILED, None, 8),
        (None, None, None, None, InvoiceStatus.UPLOADED, None, 0),
        ("NOS-88431", vendors[0].name, pos[0].po_number, "1098.25", InvoiceStatus.PROCESSING, None, 3),
    ]
    for number, vendor, po, amount, status, confidence, days in samples:
        created = now - timedelta(days=days, hours=2)
        invoice = Invoice(invoice_number=number, vendor_name=vendor, po_number=po, invoice_date=date.today()-timedelta(days=days+3) if number else None, total_amount=Decimal(amount) if amount else None, file_path=f"/app/uploads/demo-{number or 'upload'}.pdf", extraction_confidence=confidence, status=status, created_at=created, updated_at=created)
        db.add(invoice)
        db.flush()
        db.add(AuditEvent(invoice_id=invoice.id, event_type="INVOICE_UPLOADED", message="Invoice file was uploaded.", created_at=created))
        if number:
            db.add(AuditEvent(invoice_id=invoice.id, event_type="DETAILS_RECORDED", message="Invoice details were recorded for demonstration purposes.", created_at=created+timedelta(minutes=2)))
        if status == InvoiceStatus.NEEDS_REVIEW:
            db.add(InvoiceException(invoice_id=invoice.id, exception_type=ExceptionType.AMOUNT_MISMATCH, description="Invoice amount exceeds the remaining purchase order balance.", expected_value="$9,190.00", actual_value="$9,450.00", created_at=created+timedelta(minutes=3)))
            db.add(AuditEvent(invoice_id=invoice.id, event_type="REVIEW_REQUIRED", message="Invoice was routed for manual review due to an amount mismatch.", created_at=created+timedelta(minutes=3)))
        elif status not in {InvoiceStatus.UPLOADED, InvoiceStatus.PROCESSING}:
            db.add(AuditEvent(invoice_id=invoice.id, event_type=f"INVOICE_{status.value}", message=f"Invoice status changed to {status.value.replace('_', ' ').title()}.", created_at=created+timedelta(minutes=4)))
    db.commit()

