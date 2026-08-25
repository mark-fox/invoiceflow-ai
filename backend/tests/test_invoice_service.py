from io import BytesIO
from pathlib import Path
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.core.config import settings
from app.db.session import Base
from app.models import AuditEvent, ExceptionType, Invoice, InvoiceException, InvoiceStatus
from app.schemas.models import ProcessingExceptionIn, ProcessingResultIn
from app.services.invoices import (
    apply_processing_result,
    review_invoice,
    save_upload,
    start_invoice_processing,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def upload(filename: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content), headers=Headers({"content-type": content_type}))


def processing_result(**overrides) -> ProcessingResultIn:
    values = {
        "invoice_number": "INV-2026-4001",
        "vendor_name": "Northstar Office Supply",
        "po_number": "PO-2026-1048",
        "invoice_date": date(2026, 8, 15),
        "total_amount": Decimal("4280.50"),
        "extraction_confidence": Decimal("0.98"),
        "status": InvoiceStatus.CLEARED,
        "exceptions": [],
    }
    values.update(overrides)
    return ProcessingResultIn(**values)


def test_upload_persists_invoice_and_audit_event(db: Session, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    invoice = save_upload(db, upload("vendor-invoice.pdf", "application/pdf", b"%PDF-1.7\nexample"))

    assert invoice.status == InvoiceStatus.UPLOADED
    assert Path(invoice.file_path).is_file()
    event = db.scalar(select(AuditEvent).where(AuditEvent.invoice_id == invoice.id))
    assert event is not None
    assert event.event_metadata["original_filename"] == "vendor-invoice.pdf"


def test_upload_rejects_spoofed_content_and_removes_file(db: Session, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    with pytest.raises(HTTPException) as error:
        save_upload(db, upload("not-really.pdf", "application/pdf", b"plain text"))

    assert error.value.status_code == 415
    assert list(tmp_path.iterdir()) == []


def test_review_creates_audit_event_and_prevents_second_decision(db: Session) -> None:
    invoice = Invoice(file_path="/tmp/example.pdf", status=InvoiceStatus.NEEDS_REVIEW)
    db.add(invoice)
    db.commit()

    review_invoice(db, invoice, InvoiceStatus.APPROVED)

    assert invoice.status == InvoiceStatus.APPROVED
    event = db.scalar(select(AuditEvent).where(AuditEvent.invoice_id == invoice.id))
    assert event is not None
    assert event.event_type == "INVOICE_APPROVED"
    with pytest.raises(HTTPException) as error:
        review_invoice(db, invoice, InvoiceStatus.REJECTED)
    assert error.value.status_code == 409


def test_start_processing_updates_uploaded_invoice_and_records_audit_event(db: Session) -> None:
    invoice = Invoice(file_path="/tmp/uploaded.pdf", status=InvoiceStatus.UPLOADED)
    db.add(invoice)
    db.commit()

    updated_invoice = start_invoice_processing(db, invoice, "execution-1001")

    assert updated_invoice.status == InvoiceStatus.PROCESSING
    assert updated_invoice.processing_idempotency_key == "execution-1001"
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.invoice_id == invoice.id,
            AuditEvent.event_type == "INVOICE_PROCESSING_STARTED",
        )
    )
    assert event is not None
    assert event.message == "Automated invoice processing started."
    assert event.event_metadata == {
        "idempotency_key": "execution-1001",
        "workflow_execution_id": "execution-1001",
    }

    replayed_invoice = start_invoice_processing(db, invoice, "execution-1001")
    start_events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.invoice_id == invoice.id,
            AuditEvent.event_type == "INVOICE_PROCESSING_STARTED",
        )
    ).all()
    assert replayed_invoice.id == invoice.id
    assert len(start_events) == 1


def test_start_processing_rejects_different_idempotency_key(db: Session) -> None:
    invoice = Invoice(file_path="/tmp/uploaded.pdf", status=InvoiceStatus.UPLOADED)
    db.add(invoice)
    db.commit()
    start_invoice_processing(db, invoice, "execution-1002")

    with pytest.raises(HTTPException) as error:
        start_invoice_processing(db, invoice, "different-execution")

    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "invoice_status",
    [InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.APPROVED, InvoiceStatus.FAILED],
)
def test_start_processing_rejects_non_uploaded_statuses(
    db: Session, invoice_status: InvoiceStatus
) -> None:
    invoice = Invoice(file_path="/tmp/not-uploaded.pdf", status=invoice_status)
    db.add(invoice)
    db.commit()

    with pytest.raises(HTTPException) as error:
        start_invoice_processing(db, invoice, "execution-invalid-status")

    assert error.value.status_code == 409
    assert invoice.status == invoice_status


def test_apply_processing_result_clears_invoice_and_saves_extracted_fields(
    db: Session,
) -> None:
    invoice = Invoice(
        file_path="/tmp/processing.pdf",
        status=InvoiceStatus.UPLOADED,
    )
    db.add(invoice)
    db.commit()
    start_invoice_processing(db, invoice, "execution-cleared")

    updated_invoice = apply_processing_result(
        db, invoice, processing_result(), "execution-cleared"
    )

    assert updated_invoice.status == InvoiceStatus.CLEARED
    assert updated_invoice.invoice_number == "INV-2026-4001"
    assert updated_invoice.vendor_name == "Northstar Office Supply"
    assert updated_invoice.po_number == "PO-2026-1048"
    assert updated_invoice.invoice_date == date(2026, 8, 15)
    assert updated_invoice.total_amount == Decimal("4280.50")
    assert updated_invoice.extraction_confidence == Decimal("0.98")
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.invoice_id == invoice.id,
            AuditEvent.event_type == "INVOICE_PROCESSING_COMPLETED",
        )
    )
    assert event is not None
    assert event.event_metadata["workflow_execution_id"] == "execution-cleared"
    assert event.event_metadata["resulting_status"] == "CLEARED"
    assert event.event_metadata["exception_count"] == 0


def test_apply_processing_result_persists_review_exceptions(db: Session) -> None:
    invoice = Invoice(
        file_path="/tmp/review.pdf",
        status=InvoiceStatus.PROCESSING,
        processing_idempotency_key="execution-review",
    )
    db.add(invoice)
    db.commit()
    result = processing_result(
        status=InvoiceStatus.NEEDS_REVIEW,
        exceptions=[
            ProcessingExceptionIn(
                exception_type=ExceptionType.AMOUNT_MISMATCH,
                description="Invoice amount differs from the purchase order.",
                expected_value="4280.50",
                actual_value="4380.50",
            )
        ],
    )

    apply_processing_result(db, invoice, result, "execution-review")

    assert invoice.status == InvoiceStatus.NEEDS_REVIEW
    saved_exception = db.scalar(
        select(InvoiceException).where(InvoiceException.invoice_id == invoice.id)
    )
    assert saved_exception is not None
    assert saved_exception.exception_type == ExceptionType.AMOUNT_MISMATCH
    assert saved_exception.expected_value == "4280.50"
    assert saved_exception.actual_value == "4380.50"
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.invoice_id == invoice.id,
            AuditEvent.event_type == "INVOICE_PROCESSING_COMPLETED",
        )
    )
    assert event is not None
    assert event.event_metadata == {
        "workflow_execution_id": "execution-review",
        "resulting_status": "NEEDS_REVIEW",
        "exception_count": 1,
    }

    replayed_invoice = apply_processing_result(
        db, invoice, result, "execution-review"
    )
    saved_exceptions = db.scalars(
        select(InvoiceException).where(InvoiceException.invoice_id == invoice.id)
    ).all()
    completion_events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.invoice_id == invoice.id,
            AuditEvent.event_type == "INVOICE_PROCESSING_COMPLETED",
        )
    ).all()
    assert replayed_invoice.status == InvoiceStatus.NEEDS_REVIEW
    assert len(saved_exceptions) == 1
    assert len(completion_events) == 1


def test_apply_processing_result_can_fail_processing(db: Session) -> None:
    invoice = Invoice(
        file_path="/tmp/failed.pdf",
        status=InvoiceStatus.PROCESSING,
        processing_idempotency_key="execution-failed",
    )
    db.add(invoice)
    db.commit()

    apply_processing_result(
        db,
        invoice,
        processing_result(
            status=InvoiceStatus.FAILED,
            invoice_number=None,
            vendor_name=None,
            po_number=None,
            invoice_date=None,
            total_amount=None,
            extraction_confidence=None,
        ),
        "execution-failed",
    )

    assert invoice.status == InvoiceStatus.FAILED


def test_apply_processing_result_rejects_invalid_lifecycle_and_repeat(
    db: Session,
) -> None:
    uploaded_invoice = Invoice(
        file_path="/tmp/uploaded-result.pdf", status=InvoiceStatus.UPLOADED
    )
    processing_invoice = Invoice(
        file_path="/tmp/completed-result.pdf",
        status=InvoiceStatus.PROCESSING,
        processing_idempotency_key="execution-completed",
    )
    db.add_all([uploaded_invoice, processing_invoice])
    db.commit()

    with pytest.raises(HTTPException) as uploaded_error:
        apply_processing_result(
            db, uploaded_invoice, processing_result(), "execution-uploaded"
        )
    assert uploaded_error.value.status_code == 409

    apply_processing_result(
        db, processing_invoice, processing_result(), "execution-completed"
    )
    replayed_invoice = apply_processing_result(
        db, processing_invoice, processing_result(), "execution-completed"
    )
    assert replayed_invoice.status == InvoiceStatus.CLEARED
    with pytest.raises(HTTPException) as different_key_error:
        apply_processing_result(
            db, processing_invoice, processing_result(), "different-execution"
        )
    assert different_key_error.value.status_code == 409


def test_apply_processing_result_rejects_different_idempotency_key(
    db: Session,
) -> None:
    invoice = Invoice(
        file_path="/tmp/key-mismatch.pdf",
        status=InvoiceStatus.UPLOADED,
    )
    db.add(invoice)
    db.commit()
    start_invoice_processing(db, invoice, "established-execution")

    with pytest.raises(HTTPException) as error:
        apply_processing_result(
            db, invoice, processing_result(), "different-execution"
        )

    assert error.value.status_code == 409
    assert invoice.status == InvoiceStatus.PROCESSING


@pytest.mark.parametrize("invalid_status", [InvoiceStatus.APPROVED, InvoiceStatus.REJECTED])
def test_processing_result_rejects_manual_review_statuses(
    invalid_status: InvoiceStatus,
) -> None:
    with pytest.raises(ValidationError):
        processing_result(status=invalid_status)


@pytest.mark.parametrize("invalid_confidence", [Decimal("-0.01"), Decimal("1.01")])
def test_processing_result_rejects_out_of_range_confidence(
    invalid_confidence: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        processing_result(extraction_confidence=invalid_confidence)
