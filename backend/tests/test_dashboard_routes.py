from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.dashboard import (
    get_automation_metrics,
    get_automation_summary,
    get_recent_processing,
)
from app.db.session import Base
from app.models import AuditEvent, ExceptionType, Invoice, InvoiceException, InvoiceStatus


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def test_automation_summary_aggregates_invoices_and_exceptions(db: Session) -> None:
    invoices = [
        Invoice(file_path="uploads/uploaded-1.pdf", status=InvoiceStatus.UPLOADED),
        Invoice(file_path="uploads/uploaded-2.pdf", status=InvoiceStatus.UPLOADED),
        Invoice(file_path="uploads/processing.pdf", status=InvoiceStatus.PROCESSING),
        Invoice(file_path="uploads/cleared-1.pdf", status=InvoiceStatus.CLEARED),
        Invoice(file_path="uploads/cleared-2.pdf", status=InvoiceStatus.CLEARED),
        Invoice(file_path="uploads/review.pdf", status=InvoiceStatus.NEEDS_REVIEW),
        Invoice(file_path="uploads/approved.pdf", status=InvoiceStatus.APPROVED),
    ]
    db.add_all(invoices)
    db.flush()
    db.add_all(
        [
            InvoiceException(
                invoice_id=invoices[5].id,
                exception_type=ExceptionType.AMOUNT_MISMATCH,
                description="Invoice and purchase order totals differ.",
            ),
            InvoiceException(
                invoice_id=invoices[5].id,
                exception_type=ExceptionType.AMOUNT_MISMATCH,
                description="A second amount mismatch was recorded.",
            ),
            InvoiceException(
                invoice_id=invoices[5].id,
                exception_type=ExceptionType.UNKNOWN_PO,
                description="Purchase order was not found.",
            ),
            InvoiceException(
                invoice_id=invoices[5].id,
                exception_type=ExceptionType.DUPLICATE_INVOICE,
                description="A matching invoice exists.",
            ),
        ]
    )
    db.commit()

    result = get_automation_summary(db)

    assert result.invoice_counts.model_dump() == {
        "total": 7,
        "uploaded": 2,
        "processing": 1,
        "cleared": 2,
        "needs_review": 1,
        "failed": 0,
        "approved": 1,
        "rejected": 0,
    }
    assert result.exception_counts == {
        ExceptionType.AMOUNT_MISMATCH: 2,
        ExceptionType.UNKNOWN_PO: 1,
        ExceptionType.DUPLICATE_INVOICE: 1,
        ExceptionType.LOW_CONFIDENCE: 0,
        ExceptionType.MISSING_FIELD: 0,
    }


def test_automation_summary_returns_all_zero_counts_for_empty_database(
    db: Session,
) -> None:
    result = get_automation_summary(db)

    assert result.invoice_counts.model_dump() == {
        "total": 0,
        "uploaded": 0,
        "processing": 0,
        "cleared": 0,
        "needs_review": 0,
        "failed": 0,
        "approved": 0,
        "rejected": 0,
    }
    assert result.exception_counts == {
        exception_type: 0 for exception_type in ExceptionType
    }


def test_recent_processing_returns_only_completions_newest_first(
    db: Session,
) -> None:
    older_invoice = Invoice(
        file_path="uploads/older.pdf",
        invoice_number="INV-1001",
        vendor_name="Northstar Parts",
        status=InvoiceStatus.CLEARED,
    )
    newer_invoice = Invoice(
        file_path="uploads/newer.pdf",
        invoice_number=None,
        vendor_name=None,
        status=InvoiceStatus.NEEDS_REVIEW,
    )
    db.add_all([older_invoice, newer_invoice])
    db.flush()

    base_time = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)
    db.add_all(
        [
            AuditEvent(
                invoice_id=older_invoice.id,
                event_type="INVOICE_PROCESSING_COMPLETED",
                message="Processing completed.",
                created_at=base_time,
            ),
            AuditEvent(
                invoice_id=newer_invoice.id,
                event_type="INVOICE_PROCESSING_COMPLETED",
                message="Processing completed.",
                created_at=base_time + timedelta(minutes=10),
            ),
            AuditEvent(
                invoice_id=older_invoice.id,
                event_type="INVOICE_PROCESSING_STARTED",
                message="Processing started.",
                created_at=base_time + timedelta(minutes=20),
            ),
            AuditEvent(
                invoice_id=older_invoice.id,
                event_type="INVOICE_APPROVED",
                message="Invoice approved.",
                created_at=base_time + timedelta(minutes=30),
            ),
            InvoiceException(
                invoice_id=newer_invoice.id,
                exception_type=ExceptionType.UNKNOWN_PO,
                description="Purchase order was not found.",
            ),
            InvoiceException(
                invoice_id=newer_invoice.id,
                exception_type=ExceptionType.LOW_CONFIDENCE,
                description="Extraction confidence was below the threshold.",
            ),
        ]
    )
    db.commit()

    result = get_recent_processing(db)

    assert [item.invoice_id for item in result] == [
        newer_invoice.id,
        older_invoice.id,
    ]
    assert result[0].invoice_number is None
    assert result[0].vendor_name is None
    assert result[0].status == InvoiceStatus.NEEDS_REVIEW
    assert result[0].exception_count == 2
    assert result[1].invoice_number == "INV-1001"
    assert result[1].vendor_name == "Northstar Parts"
    assert result[1].status == InvoiceStatus.CLEARED
    assert result[1].exception_count == 0


def test_recent_processing_returns_empty_list_for_empty_database(db: Session) -> None:
    assert get_recent_processing(db) == []


def test_recent_processing_limits_results_to_ten(db: Session) -> None:
    base_time = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)
    invoices = [
        Invoice(
            file_path=f"uploads/invoice-{index}.pdf",
            status=InvoiceStatus.CLEARED,
        )
        for index in range(12)
    ]
    db.add_all(invoices)
    db.flush()
    db.add_all(
        [
            AuditEvent(
                invoice_id=invoice.id,
                event_type="INVOICE_PROCESSING_COMPLETED",
                message="Processing completed.",
                created_at=base_time + timedelta(minutes=index),
            )
            for index, invoice in enumerate(invoices)
        ]
    )
    db.commit()

    result = get_recent_processing(db)

    assert len(result) == 10
    assert [item.invoice_id for item in result] == [
        invoice.id for invoice in reversed(invoices[2:])
    ]


def test_automation_metrics_returns_zeros_without_completions(db: Session) -> None:
    result = get_automation_metrics(db)

    assert result.model_dump() == {
        "completed_count": 0,
        "auto_cleared_count": 0,
        "needs_review_count": 0,
        "failed_count": 0,
        "auto_clear_rate": 0.0,
        "review_rate": 0.0,
        "failure_rate": 0.0,
        "average_processing_seconds": None,
    }


def test_automation_metrics_uses_historical_outcomes_and_paired_runs(
    db: Session,
) -> None:
    invoice = Invoice(
        file_path="uploads/historical.pdf",
        status=InvoiceStatus.APPROVED,
    )
    db.add(invoice)
    db.flush()
    base_time = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)

    events: list[AuditEvent] = []
    for index, (execution_id, resulting_status, duration_seconds) in enumerate(
        [
            ("execution-cleared", "CLEARED", 10),
            ("execution-review", "NEEDS_REVIEW", 20),
            ("execution-failed", "FAILED", 30),
        ]
    ):
        started_at = base_time + timedelta(minutes=index * 10)
        events.extend(
            [
                AuditEvent(
                    invoice_id=invoice.id,
                    event_type="INVOICE_PROCESSING_STARTED",
                    message="Processing started.",
                    event_metadata={"workflow_execution_id": execution_id},
                    created_at=started_at,
                ),
                AuditEvent(
                    invoice_id=invoice.id,
                    event_type="INVOICE_PROCESSING_COMPLETED",
                    message="Processing completed.",
                    event_metadata={
                        "workflow_execution_id": execution_id,
                        "resulting_status": resulting_status,
                    },
                    created_at=started_at + timedelta(seconds=duration_seconds),
                ),
            ]
        )

    events.extend(
        [
            AuditEvent(
                invoice_id=invoice.id,
                event_type="INVOICE_PROCESSING_STARTED",
                message="Processing started without completion.",
                event_metadata={"workflow_execution_id": "unmatched-start"},
                created_at=base_time + timedelta(hours=1),
            ),
            AuditEvent(
                invoice_id=invoice.id,
                event_type="INVOICE_PROCESSING_COMPLETED",
                message="Processing completed without a matching start.",
                event_metadata={
                    "workflow_execution_id": "unmatched-completion",
                    "resulting_status": "CLEARED",
                },
                created_at=base_time + timedelta(hours=2),
            ),
        ]
    )
    db.add_all(events)
    db.commit()

    result = get_automation_metrics(db)

    assert result.completed_count == 4
    assert result.auto_cleared_count == 2
    assert result.needs_review_count == 1
    assert result.failed_count == 1
    assert result.auto_clear_rate == pytest.approx(0.5)
    assert result.review_rate == pytest.approx(0.25)
    assert result.failure_rate == pytest.approx(0.25)
    assert result.average_processing_seconds == pytest.approx(20.0)
