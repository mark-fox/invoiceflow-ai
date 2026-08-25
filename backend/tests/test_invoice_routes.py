import asyncio
from io import BytesIO

import httpx
import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.api.routes import invoices as invoice_routes
from app.api.routes.invoices import check_duplicate_invoice, router
from app.core.config import settings
from app.db.session import Base
from app.models import Invoice, InvoiceStatus


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def api_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/invoices")
    return TestClient(app)


def add_invoice(
    db: Session, invoice_number: str, vendor_name: str
) -> Invoice:
    invoice = Invoice(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        file_path="/tmp/invoice.pdf",
        status=InvoiceStatus.CLEARED,
    )
    db.add(invoice)
    db.commit()
    return invoice


def invoice_upload() -> UploadFile:
    return UploadFile(
        filename="invoice.pdf",
        file=BytesIO(b"%PDF-1.7\ntest invoice"),
        headers=Headers({"content-type": "application/pdf"}),
    )


def test_upload_dispatches_committed_invoice_id(monkeypatch) -> None:
    sequence = []
    invoice = Invoice(id=73, file_path="/tmp/invoice.pdf", status=InvoiceStatus.UPLOADED)

    def fake_save_upload(db, file):
        sequence.append("committed")
        return invoice

    async def fake_dispatch(invoice_id: int) -> None:
        assert sequence == ["committed"]
        sequence.append(("dispatched", invoice_id))

    monkeypatch.setattr(invoice_routes, "save_upload", fake_save_upload)
    monkeypatch.setattr(invoice_routes, "dispatch_invoice_uploaded", fake_dispatch)
    monkeypatch.setattr(invoice_routes, "_detail", lambda db, invoice_id: invoice)

    result = asyncio.run(invoice_routes.upload_invoice(invoice_upload(), object()))

    assert result.id == 73
    assert sequence == ["committed", ("dispatched", 73)]


def test_upload_failure_does_not_dispatch(monkeypatch) -> None:
    dispatched = False

    def fake_save_upload(db, file):
        raise HTTPException(status_code=415, detail="Invalid invoice file.")

    async def fake_dispatch(invoice_id: int) -> None:
        nonlocal dispatched
        dispatched = True

    monkeypatch.setattr(invoice_routes, "save_upload", fake_save_upload)
    monkeypatch.setattr(invoice_routes, "dispatch_invoice_uploaded", fake_dispatch)

    with pytest.raises(HTTPException):
        asyncio.run(invoice_routes.upload_invoice(invoice_upload(), object()))

    assert dispatched is False


def test_dispatch_failure_preserves_uploaded_invoice(
    db: Session, tmp_path, monkeypatch, caplog
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    async def failed_dispatch(invoice_id: int) -> None:
        raise httpx.ConnectError("n8n unavailable")

    monkeypatch.setattr(invoice_routes, "dispatch_invoice_uploaded", failed_dispatch)

    with caplog.at_level("ERROR"):
        response = asyncio.run(invoice_routes.upload_invoice(invoice_upload(), db))

    stored_invoice = db.scalar(select(Invoice).where(Invoice.id == response.id))
    assert stored_invoice is not None
    assert stored_invoice.status == InvoiceStatus.UPLOADED
    assert "invoice remains uploaded" in caplog.text


def test_duplicate_check_returns_matching_invoice_id(db: Session) -> None:
    invoice = add_invoice(db, "INV-1001", "Northstar Office Supply")

    result = check_duplicate_invoice(
        invoice_number="INV-1001",
        vendor_name="Northstar Office Supply",
        db=db,
    )

    assert result.is_duplicate is True
    assert result.matching_invoice_id == invoice.id


def test_duplicate_check_can_exclude_current_invoice(db: Session) -> None:
    invoice = add_invoice(db, "INV-1002", "Summit IT Solutions")

    result = check_duplicate_invoice(
        invoice_number="INV-1002",
        vendor_name="Summit IT Solutions",
        exclude_invoice_id=invoice.id,
        db=db,
    )

    assert result.is_duplicate is False
    assert result.matching_invoice_id is None


def test_duplicate_check_requires_same_vendor(db: Session) -> None:
    add_invoice(db, "INV-1003", "Harbor Facilities Group")

    result = check_duplicate_invoice(
        invoice_number="INV-1003",
        vendor_name="Different Vendor",
        db=db,
    )

    assert result.is_duplicate is False
    assert result.matching_invoice_id is None


def test_duplicate_check_returns_false_when_no_invoice_matches(db: Session) -> None:
    result = check_duplicate_invoice(
        invoice_number="INV-DOES-NOT-EXIST",
        vendor_name="Unknown Vendor",
        db=db,
    )

    assert result.is_duplicate is False
    assert result.matching_invoice_id is None


@pytest.mark.parametrize(
    ("path", "json_body"),
    [
        ("/api/invoices/1/processing/start", None),
        (
            "/api/invoices/1/processing/result",
            {
                "invoice_number": None,
                "vendor_name": None,
                "po_number": None,
                "invoice_date": None,
                "total_amount": None,
                "extraction_confidence": None,
                "status": "FAILED",
                "exceptions": [],
            },
        ),
    ],
)
def test_automation_mutations_require_idempotency_key(
    api_client: TestClient, path: str, json_body: dict | None
) -> None:
    response = api_client.post(path, json=json_body)

    assert response.status_code == 422
    assert any(
        error["loc"] == ["header", "Idempotency-Key"]
        for error in response.json()["detail"]
    )
