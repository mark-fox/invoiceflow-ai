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
from app.services.invoices import review_invoice, save_upload


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
