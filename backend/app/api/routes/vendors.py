from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Vendor
from app.schemas.models import VendorOut

router = APIRouter()


@router.get("", response_model=list[VendorOut])
def list_vendors(db: Session = Depends(get_db)) -> list[Vendor]:
    return list(db.scalars(select(Vendor).order_by(Vendor.name)).all())

