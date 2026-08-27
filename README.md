# InvoiceFlow AI

InvoiceFlow AI is an AI-assisted Accounts Payable automation application that processes uploaded invoices, extracts structured invoice data, validates it against purchase-order records, routes exceptions for human review, and records a complete audit trail.

The project combines a conventional web application with an event-driven n8n workflow. FastAPI and PostgreSQL remain the system of record, while n8n orchestrates AI extraction and deterministic processing rules.

## What it does

InvoiceFlow AI supports an end-to-end invoice-processing workflow:

1. A user uploads a PDF or image invoice in the React application.
2. FastAPI persists the invoice in PostgreSQL with status `UPLOADED`.
3. After the database transaction commits, the backend calls the published n8n production webhook.
4. n8n transitions the invoice to `PROCESSING` and downloads the source document from FastAPI.
5. OpenAI extracts structured invoice fields using a strict JSON schema.
6. Deterministic rules validate the extraction and purchase-order data.
7. The invoice is routed to:
   - `CLEARED` when validation succeeds
   - `NEEDS_REVIEW` when a business exception is detected
   - `FAILED` when AI extraction cannot be completed
8. Human reviewers can approve or reject invoices that require review.
9. Audit events, exceptions, processing metrics, and recent automation activity remain visible in the application.

The LLM is responsible only for document extraction. Business decisions are performed by explicit deterministic rules.

## Automation rules

The current workflow checks for:

- Missing required fields
- Low extraction confidence
- Duplicate invoice number and vendor
- Unknown purchase order
- Invoice / purchase-order amount mismatch

Supported exception types include:

- `AMOUNT_MISMATCH`
- `UNKNOWN_PO`
- `DUPLICATE_INVOICE`
- `LOW_CONFIDENCE`
- `MISSING_FIELD`

## Reliability and recovery

The automation flow includes several production-minded safeguards:

- **Webhook-driven processing** — invoices trigger n8n after upload rather than relying on polling.
- **Database-first dispatch** — n8n is called only after the uploaded invoice has been committed.
- **Idempotency** — n8n sends its execution ID as an `Idempotency-Key`, preventing duplicate processing side effects during retries.
- **AI retries** — transient OpenAI failures are retried before the invoice is marked `FAILED`.
- **Explicit failure handling** — exhausted AI failures terminate the invoice cleanly instead of leaving it stuck in `PROCESSING`.
- **Dispatch recovery** — invoices remain `UPLOADED` if n8n cannot be reached and can be redispatched with the **Retry Processing** action.
- **Temporary frontend polling** — invoice detail pages automatically refresh while an invoice is `UPLOADED` or `PROCESSING`.
- **Audit correlation** — processing audit events record the n8n workflow execution identifier.
- **Row locking and lifecycle guards** — backend mutation endpoints enforce valid processing transitions.

## Human review

Invoices routed to `NEEDS_REVIEW` display their exception details and can be manually:

- Approved
- Rejected

The original exception and audit history remain available after review so the processing decision is traceable.

## Operations dashboard

The dashboard provides visibility into the automation system, including:

- Invoice counts by processing status
- Exception counts by type
- Auto-clear rate
- Human-review rate
- Failure rate
- Average processing time
- Recent automated processing completions
- Exception counts for recent invoices

## Stack

### Frontend

- React
- TypeScript
- Vite
- React Router
- Lucide icons

### Backend

- FastAPI
- Python
- SQLAlchemy 2
- Alembic
- PostgreSQL

### Automation / AI

- n8n
- OpenAI structured-output extraction
- Deterministic routing rules

### Infrastructure

- Docker Compose
- Persistent PostgreSQL storage
- Persistent uploaded-document storage
- Persistent n8n instance data

## Project structure

```text
backend/                    FastAPI routes, services, models, schemas, migrations, tests
frontend/                   React pages, components, hooks, typed REST client, styles
n8n/workflows/              Exported n8n workflow definitions
docker-compose.yml          Local application, database, and n8n services
```

The backend owns all application state. PostgreSQL is the source of truth, uploaded documents are stored in a persistent Docker volume, and the frontend communicates through the REST API.

n8n runs on the same Docker Compose network and reaches FastAPI at:

```text
http://backend:8000
```

FastAPI reaches the published n8n webhook at:

```text
http://n8n:5678/webhook/invoice-uploaded
```

## Run locally

### Prerequisites

- Docker Desktop
- Docker Compose
- An OpenAI API key configured as an n8n OpenAI credential

### Start the application

```bash
cp .env.example .env
docker compose up --build
```

On PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Local services:

- Application: http://localhost:5173
- API documentation: http://localhost:8000/docs
- API health check: http://localhost:8000/health
- n8n: http://localhost:5678

Alembic migrations run when the backend starts. Demo data is inserted only when the configured seed conditions are met. Set `SEED_DEMO_DATA=false` in `.env` to disable demo-data creation.

To stop the application:

```bash
docker compose down
```

Add `-v` only when you intentionally want to remove local database, uploaded-file, and other named volumes.

## n8n setup

The repository contains the exported invoice-processing workflow under:

```text
n8n/workflows/
```

Import the workflow into n8n, configure the OpenAI credential, and verify that the workflow uses the shared Docker-network backend URL:

```text
http://backend:8000
```

The workflow begins with the production webhook path:

```text
/webhook/invoice-uploaded
```

## Main REST API surface

### Invoices

- `GET /api/invoices`
- `POST /api/invoices/upload`
- `GET /api/invoices/{id}`
- `GET /api/invoices/{id}/file`
- `POST /api/invoices/{id}/approve`
- `POST /api/invoices/{id}/reject`
- `POST /api/invoices/{id}/processing/dispatch`
- `POST /api/invoices/{id}/processing/start`
- `POST /api/invoices/{id}/processing/result`
- `GET /api/invoices/duplicate-check`

### Purchase orders

- `GET /api/purchase-orders`
- `GET /api/purchase-orders/by-number/{po_number}`

### Vendors

- `GET /api/vendors`

### Dashboard / operations

- `GET /api/dashboard`
- `GET /api/dashboard/automation-summary`
- `GET /api/dashboard/recent-processing`
- `GET /api/dashboard/automation-metrics`

Interactive API documentation is available at:

```text
http://localhost:8000/docs
```

## Processing lifecycle

```text
UPLOADED
   |
   v
PROCESSING
   |
   +----> CLEARED
   |
   +----> NEEDS_REVIEW ----> APPROVED
   |                    |
   |                    +--> REJECTED
   |
   +----> FAILED
```

FastAPI enforces lifecycle transitions. n8n does not directly mutate the database; it uses backend API endpoints.

## Demo scenarios verified

The workflow has been exercised end-to-end with representative scenarios including:

- Valid invoice that automatically clears
- Invoice / PO amount mismatch
- Unknown purchase order
- Duplicate invoice
- Missing required invoice field
- Manual approval
- Manual rejection
- AI extraction failure handling
- Workflow redispatch after an automation-dispatch failure

## Design principles

InvoiceFlow AI intentionally separates responsibilities:

- **React** provides the user-facing review workspace.
- **FastAPI** owns application state, lifecycle validation, transactions, and audit persistence.
- **PostgreSQL** is the source of truth.
- **n8n** orchestrates the automation workflow.
- **OpenAI** extracts structured data from invoice documents.
- **Deterministic application rules** make business-routing decisions.

This separation keeps AI behavior bounded while making the automation observable, testable, recoverable, and easier to reason about.
