from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditEvent, ExceptionType, Invoice, InvoiceException, InvoiceStatus
from app.schemas.models import (
    AutomationInvoiceCounts,
    AutomationMetrics,
    AutomationSummary,
    DashboardSummary,
    RecentProcessingItem,
)

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


@router.get("/automation-metrics", response_model=AutomationMetrics)
def get_automation_metrics(db: Session = Depends(get_db)) -> AutomationMetrics:
    resulting_status = AuditEvent.event_metadata["resulting_status"].as_string()
    (
        completed_count,
        auto_cleared_count,
        needs_review_count,
        failed_count,
    ) = db.execute(
        select(
            func.count(AuditEvent.id),
            func.coalesce(
                func.sum(
                    case(
                        (resulting_status == InvoiceStatus.CLEARED.value, 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (resulting_status == InvoiceStatus.NEEDS_REVIEW.value, 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (resulting_status == InvoiceStatus.FAILED.value, 1),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(AuditEvent.event_type == "INVOICE_PROCESSING_COMPLETED")
    ).one()

    workflow_execution_id = AuditEvent.event_metadata[
        "workflow_execution_id"
    ].as_string()
    started_runs = (
        select(
            AuditEvent.invoice_id.label("invoice_id"),
            workflow_execution_id.label("workflow_execution_id"),
            func.min(AuditEvent.created_at).label("started_at"),
            func.count(AuditEvent.id).label("event_count"),
        )
        .where(
            AuditEvent.event_type == "INVOICE_PROCESSING_STARTED",
            workflow_execution_id.is_not(None),
        )
        .group_by(AuditEvent.invoice_id, workflow_execution_id)
        .subquery()
    )
    completed_runs = (
        select(
            AuditEvent.invoice_id.label("invoice_id"),
            workflow_execution_id.label("workflow_execution_id"),
            func.min(AuditEvent.created_at).label("completed_at"),
            func.count(AuditEvent.id).label("event_count"),
        )
        .where(
            AuditEvent.event_type == "INVOICE_PROCESSING_COMPLETED",
            workflow_execution_id.is_not(None),
        )
        .group_by(AuditEvent.invoice_id, workflow_execution_id)
        .subquery()
    )
    paired_timestamps = db.execute(
        select(started_runs.c.started_at, completed_runs.c.completed_at)
        .join(
            completed_runs,
            and_(
                completed_runs.c.invoice_id == started_runs.c.invoice_id,
                completed_runs.c.workflow_execution_id
                == started_runs.c.workflow_execution_id,
            ),
        )
        .where(
            started_runs.c.event_count == 1,
            completed_runs.c.event_count == 1,
            completed_runs.c.completed_at >= started_runs.c.started_at,
        )
    ).all()

    average_processing_seconds = None
    if paired_timestamps:
        average_processing_seconds = sum(
            (completed_at - started_at).total_seconds()
            for started_at, completed_at in paired_timestamps
        ) / len(paired_timestamps)

    return AutomationMetrics(
        completed_count=completed_count,
        auto_cleared_count=auto_cleared_count,
        needs_review_count=needs_review_count,
        failed_count=failed_count,
        auto_clear_rate=(auto_cleared_count / completed_count if completed_count else 0),
        review_rate=(needs_review_count / completed_count if completed_count else 0),
        failure_rate=(failed_count / completed_count if completed_count else 0),
        average_processing_seconds=average_processing_seconds,
    )


@router.get("/recent-processing", response_model=list[RecentProcessingItem])
def get_recent_processing(
    db: Session = Depends(get_db),
) -> list[RecentProcessingItem]:
    exception_counts = (
        select(
            InvoiceException.invoice_id,
            func.count(InvoiceException.id).label("exception_count"),
        )
        .group_by(InvoiceException.invoice_id)
        .subquery()
    )
    rows = db.execute(
        select(
            AuditEvent.invoice_id,
            Invoice.invoice_number,
            Invoice.vendor_name,
            Invoice.status,
            AuditEvent.created_at.label("completed_at"),
            func.coalesce(exception_counts.c.exception_count, 0).label(
                "exception_count"
            ),
        )
        .join(Invoice, Invoice.id == AuditEvent.invoice_id)
        .outerjoin(
            exception_counts,
            exception_counts.c.invoice_id == Invoice.id,
        )
        .where(AuditEvent.event_type == "INVOICE_PROCESSING_COMPLETED")
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(10)
    ).mappings()

    return [RecentProcessingItem.model_validate(row) for row in rows]
