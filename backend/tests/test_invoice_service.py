from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.core.config import settings
from app.db.session import Base
from app.models import AuditEvent, Invoice, InvoiceStatus
from app.services.invoices import review_invoice, save_upload, start_invoice_processing


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def upload(filename: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content), headers=Headers({"content-type": content_type}))


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

    updated_invoice = start_invoice_processing(db, invoice)

    assert updated_invoice.status == InvoiceStatus.PROCESSING
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.invoice_id == invoice.id,
            AuditEvent.event_type == "INVOICE_PROCESSING_STARTED",
        )
    )
    assert event is not None
    assert event.message == "Automated invoice processing started."

    with pytest.raises(HTTPException) as error:
        start_invoice_processing(db, invoice)
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
        start_invoice_processing(db, invoice)

    assert error.value.status_code == 409
    assert invoice.status == invoice_status
