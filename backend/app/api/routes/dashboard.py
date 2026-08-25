from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExceptionType, Invoice, InvoiceException, InvoiceStatus
from app.schemas.models import AutomationInvoiceCounts, AutomationSummary, DashboardSummary

router = APIRouter()


@router.get("", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
    rows = db.execute(select(Invoice.status, func.count(Invoice.id)).group_by(Invoice.status)).all()
    counts = {status: count for status, count in rows}
    recent = db.scalars(select(Invoice).order_by(Invoice.created_at.desc()).limit(8)).all()
    return DashboardSummary(
        total_invoices=sum(counts.values()),
        automatically_cleared=counts.get(InvoiceStatus.CLEARED, 0),
        needs_review=counts.get(InvoiceStatus.NEEDS_REVIEW, 0),
        approved=counts.get(InvoiceStatus.APPROVED, 0),
        rejected=counts.get(InvoiceStatus.REJECTED, 0),
        failed=counts.get(InvoiceStatus.FAILED, 0),
        recent_invoices=list(recent),
    )


@router.get("/automation-summary", response_model=AutomationSummary)
def get_automation_summary(db: Session = Depends(get_db)) -> AutomationSummary:
    invoice_rows = db.execute(
        select(Invoice.status, func.count(Invoice.id)).group_by(Invoice.status)
    ).all()
    exception_rows = db.execute(
        select(InvoiceException.exception_type, func.count(InvoiceException.id)).group_by(
            InvoiceException.exception_type
        )
    ).all()

    invoice_counts = dict(invoice_rows)
    exception_counts = dict(exception_rows)

    return AutomationSummary(
        invoice_counts=AutomationInvoiceCounts(
            total=sum(invoice_counts.values()),
            uploaded=invoice_counts.get(InvoiceStatus.UPLOADED, 0),
            processing=invoice_counts.get(InvoiceStatus.PROCESSING, 0),
            cleared=invoice_counts.get(InvoiceStatus.CLEARED, 0),
            needs_review=invoice_counts.get(InvoiceStatus.NEEDS_REVIEW, 0),
            failed=invoice_counts.get(InvoiceStatus.FAILED, 0),
            approved=invoice_counts.get(InvoiceStatus.APPROVED, 0),
            rejected=invoice_counts.get(InvoiceStatus.REJECTED, 0),
        ),
        exception_counts={
            exception_type: exception_counts.get(exception_type, 0)
            for exception_type in ExceptionType
        },
    )
