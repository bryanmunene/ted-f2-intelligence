# cBrain TED F2 Intelligence

Internal TED-only tender intelligence application for cBrain staff evaluating opportunities relevant to the F2 platform.

This service is intentionally narrow:

- source of truth is the official TED public interfaces only
- primary notice discovery is the anonymous TED Search API
- scoring is deterministic, explainable, and auditable
- UI is server-rendered and deployment-oriented for enterprise hosting

## Official TED Integration Surfaces

The implementation is designed around TED's official public interfaces:

- TED Search API: `POST /v3/notices/search`
- official direct-link notice rendering and document download routes
- official XML retrieval routes
- official TED release calendar and fair-usage guidance

Reference documentation:

- https://docs.ted.europa.eu/api/latest/search.html
- https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html
- https://ted.europa.eu/en/simap/developers-corner-for-reusers
- https://docs.ted.europa.eu/ODS/latest/reuse/field-list.html

## Stack

- Backend: FastAPI
- UI: Jinja2 server-rendered templates
- Database: PostgreSQL
- ORM: SQLAlchemy 2.x
- Migrations: Alembic
- HTTP client: httpx
- Validation and settings: Pydantic / pydantic-settings
- Container target: Docker on Linux behind a reverse proxy

## Key Capabilities in This Initial Build

- canonical TED API client with retries, throttling, caching, and request accounting
- normalized notice model that isolates TED-specific payload handling
- deterministic F2-fit scoring engine with timing, positive/negative domain signals, and lock analysis
- audit-oriented persistence for notices, analyses, scan runs, notes, and events
- dashboard, scan, results, detail, and admin UI pages
- internal JSON endpoints for automation reuse
- seed configuration for keyword packs and search profiles
- initial migration and test suite

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### 2. Configure environment

```bash
copy .env.example .env
```

Update at minimum:

- `APP_SECRET_KEY`
- `APP_DATABASE_URL`
- `APP_SESSION_HTTPS_ONLY=true` in production

### 3. Start PostgreSQL and the app with Docker

```bash
docker compose up --build
```

### 4. Or run locally

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

### 5. Seed sample data

```bash
python scripts/seed_sample_data.py
```

## Temporary Streamlit UI

If you want a temporary read-only Streamlit shell while keeping FastAPI as the canonical backend design:

```bash
pip install -e .[streamlit]
streamlit run streamlit_app.py
```

The Streamlit UI reads the same database-backed notices, scores, and scan history. It is intentionally temporary and should not replace the FastAPI app for production hosting.

## Development Commands

```bash
pytest
ruff check .
mypy app
```

## Configuration Files

- `config/keyword_pack.yaml`: canonical scoring vocabulary and signal weights
- `config/search_profiles.yaml`: scan profiles and strategy presets
- `.env`: deployment-specific runtime configuration

## Security and Hosting Notes

- no secrets are stored in the repository
- session settings are environment-driven
- CSRF validation is enforced for HTML form posts
- structured logging is enabled
- health, liveness, and readiness endpoints are included
- stored data is limited to public tender metadata and internal analyst notes
- reverse-proxy header auth can be enabled later without rewriting the app

## Documentation

- `docs/architecture.md`
- `docs/scoring-rules.md`
- `docs/configuration.md`
- `docs/deployment.md`
- `docs/limitations.md`
