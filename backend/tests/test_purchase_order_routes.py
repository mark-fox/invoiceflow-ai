from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.purchase_orders import get_purchase_order_by_number
from app.db.session import Base
from app.models import PurchaseOrder, PurchaseOrderStatus, Vendor


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def test_get_purchase_order_by_number_returns_po_with_vendor(db: Session) -> None:
    vendor = Vendor(name="Acme Office Supply", vendor_code="AOS-100")
    purchase_order = PurchaseOrder(
        po_number="PO-2026-2001",
        vendor=vendor,
        total_amount=Decimal("1250.00"),
        status=PurchaseOrderStatus.OPEN,
    )
    db.add(purchase_order)
    db.commit()

    result = get_purchase_order_by_number("PO-2026-2001", db)
    db.expunge_all()

    assert result.id == purchase_order.id
    assert result.po_number == "PO-2026-2001"
    assert result.vendor.name == "Acme Office Supply"
    assert result.vendor.vendor_code == "AOS-100"


def test_get_purchase_order_by_number_returns_404_for_unknown_po(db: Session) -> None:
    with pytest.raises(HTTPException) as error:
        get_purchase_order_by_number("PO-DOES-NOT-EXIST", db)

    assert error.value.status_code == 404
    assert error.value.detail == "Purchase order not found."
