# Architecture Overview

## Goal

Deliver a production-oriented internal service that evaluates TED opportunities specifically for cBrain F2 fit.

## Core Architectural Principles

- TED official public interfaces are the only supported source surfaces.
- TED Search API is the canonical discovery mechanism.
- TED-specific request and response logic is isolated from business scoring logic.
- Scoring is deterministic, rule-based, and auditable.
- UI is server-rendered for predictable enterprise deployment and maintainability.

## Main Layers

### Web Layer

- FastAPI routes for HTML pages and internal JSON endpoints
- Jinja templates for dashboard, scan, results, detail, and admin views
- session middleware plus CSRF validation for form posts

### Service Layer

- `TedApiClient` for official Search API communication
- `TedExpertQueryBuilder` for centralized search-expression construction
- `ScanService` for scan lifecycle, orchestration, and scan-run accounting

### Ingestion Layer

- normalizes TED payloads into a stable internal notice schema
- isolates TED field naming and direct-link handling from the rest of the app

### Scoring Layer

- applies timing, keyword, strategic, and platform-lock rules
- outputs deterministic reasoning, score contributions, and qualification questions

### Persistence Layer

- PostgreSQL tables for notices, analyses, scan runs, users, notes, settings, saved searches, and audit events
- Alembic manages schema evolution

## Source-of-Truth Boundary

Only the service layer speaks TED-specific API language directly. The rest of the application works on normalized notices and score results.

