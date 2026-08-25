import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.dashboard import get_automation_summary
from app.db.session import Base
from app.models import ExceptionType, Invoice, InvoiceException, InvoiceStatus


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
