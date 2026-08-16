# InvoiceFlow AI

InvoiceFlow AI is an internal Accounts Payable application designed to become the system of record and review workspace for a later invoice-automation workflow.

## Phase 1

This phase intentionally provides only the conventional application foundation:

- Dashboard metrics and recent invoice activity
- Invoice queue with status filtering
- PDF and common image upload (15 MB limit)
- Invoice detail with PO context, exceptions, and chronological audit history
- Manual approval/rejection for invoices that need review
- Purchase order and vendor reference screens
- Realistic, idempotent demo data on first launch
- Clean REST endpoints and interactive API documentation

## Stack

React, TypeScript, Vite, FastAPI, PostgreSQL, SQLAlchemy 2, Alembic, and Docker Compose.

## Project structure

```text
backend/     FastAPI routes, business services, SQLAlchemy models, seed data, migrations
frontend/    React pages, reusable components, typed REST client, responsive styles
docker-compose.yml  Local database and application services
```

The backend owns all application data. PostgreSQL is the source of truth, uploaded documents are kept in a persistent Docker volume, and the frontend communicates only through the REST API.

## Run locally

Prerequisite: Docker Desktop with Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

On PowerShell, use `Copy-Item .env.example .env` instead of `cp` if preferred.

- Application: http://localhost:5173
- API documentation: http://localhost:8000/docs
- API health check: http://localhost:8000/health

Alembic migrations run automatically when the backend starts. Demo data is inserted only when the vendor table is empty. Set `SEED_DEMO_DATA=false` in `.env` to disable it.

To stop the application, run `docker compose down`. Add `-v` only when you intentionally want to remove the local database and uploaded-file volumes.

## REST surface

- `GET /api/dashboard`
- `GET /api/invoices?status=NEEDS_REVIEW`
- `POST /api/invoices/upload`
- `GET /api/invoices/{id}`
- `POST /api/invoices/{id}/approve`
- `POST /api/invoices/{id}/reject`
- `GET /api/purchase-orders`
- `GET /api/vendors`

These boundaries are deliberately automation-friendly so a future n8n workflow can use the API without moving workflow logic into the frontend.
