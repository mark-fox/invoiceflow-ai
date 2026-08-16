from fastapi import APIRouter

from app.api.routes import dashboard, invoices, purchase_orders, vendors

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["purchase-orders"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])

