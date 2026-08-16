from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Invoice, InvoiceStatus
from app.schemas.models import DashboardSummary

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

