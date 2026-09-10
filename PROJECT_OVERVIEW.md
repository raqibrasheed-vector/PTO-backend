# PTO Backend — Project Overview

This document summarizes the migration of the legacy **Flask** PTO application
(`PTO-Backend`) into the new **FastAPI** application (`pto_backend`), the
current state of the rewrite, and what remains to be ported.

## 1. Stack & Structure

- **Framework**: FastAPI (async), served via Uvicorn (dev, with `--reload`) or
  Gunicorn + `UvicornWorker` (prod), selected in `pto_backend/__main__.py`
  based on `settings.reload`.
- **Package manager**: `uv` (`pyproject.toml` + `uv.lock`).
- **Settings**: `pto_backend/settings.py` — Pydantic `BaseSettings`, loads
  `.env`, env vars prefixed `PTO_BACKEND_` (plus several unprefixed vars for
  ERP/SAML/Cosmos read directly via `os.getenv` for compatibility with the
  legacy `.env`).
- **Logging**: `loguru`, wired to intercept stdlib/uvicorn logging
  (`pto_backend/log.py`); a second custom colored logger exists in
  `middlewares/customlogger/customlogger.py` (singleton, used by the error
  handler decorator).
- **Docs**: Self-hosted Swagger/ReDoc at `/api/docs` and `/api/redoc`
  (`web/api/docs`), static assets served from `/static`.
- **Containerization**: `Dockerfile` + `docker-compose.yml` (dev target,
  volume-mounted, autoreload).

```
pto_backend/
├── __main__.py            # Uvicorn/Gunicorn entrypoint
├── gunicorn_runner.py      # Gunicorn app + UvicornWorker config
├── log.py                  # loguru <-> stdlib logging bridge
├── settings.py             # Pydantic settings (env-driven)
├── manager/                # Cross-cutting business/auth logic
│   ├── auth_validator/      # JWT issue + verification (TokenGatewayManager)
│   ├── saml/                 # SAML request/response handling (SAMLManager)
│   └── request_manager/      # Generic async HTTP client (httpx wrapper)
├── services/
│   ├── azure/cosmosdb/       # Cosmos DB singleton client + Pydantic table models
│   └── erp_services/         # ERP API client (token caching, employee lookup)
├── middlewares/
│   ├── errors/                # Exception -> HTTPException mapping + decorator
│   └── customlogger/          # Colorized singleton logger
└── web/
    ├── application.py        # FastAPI app factory, CORS, exception handlers
    ├── lifespan.py            # Startup/shutdown hook
    ├── enums/, types/         # Shared enums (cookie names) & shared response types
    └── api/
        ├── router.py          # Aggregates all sub-routers under /api
        ├── monitoring/        # /api/health
        ├── docs/              # /api/docs, /api/redoc, swagger oauth2 redirect
        ├── saml/               # /api/saml/* — login, ACS callback, signout, me
        └── analytics/          # /api/analytics/* — ERP employee lookup, doc upload stub
```

## 2. What Has Already Been Migrated / Improved

| Legacy (Flask) | New (FastAPI) | Notes / Improvements |
|---|---|---|
| `saml.py` (`init_saml_auth`, `saml_login`, `saml_callback`, `create_jwt_token`, `extract_token`) | `manager/saml/manager.py` (`SAMLManager`) + `web/api/saml/views.py` | Async, `python3-saml`'s `OneLogin_Saml2_Auth`; JWT now issued via a dedicated `TokenGatewayManager` (bcrypt + PyJWT) instead of ad-hoc token code. Access token now set as an **HttpOnly, Secure, SameSite=None cookie** (addresses the "store tokens in cookies not localStorage" security improvement noted in `project-improvements.md`), with a fallback to the `Authorization: Bearer` header. Added `/api/saml/me` and `/api/saml/signout` endpoints that didn't exist before. |
| `app.config["SECRET_KEY"]` / manual JWT | `manager/auth_validator/manager.py` (`TokenGatewayManager`, `TokenSchema`) | Centralized token generation/validation dependency (`validate_token_entry_point`) reusable via `Depends(...)` across all protected routes; explicit handling of expired/invalid/wrong-audience tokens with proper 401s. |
| `pto_erp_call.py` (`get_erp_data`) | `services/erp_services/manager.py` (`ErpServicesManager`) + `schema.py` | Rewritten as an async client using `httpx` (via `AsyncAPIClient`), with ERP OAuth2 token caching via `async_lru.alru_cache(ttl=1800)` (avoids re-fetching a token per request — not present in the Flask version). |
| Ad-hoc `requests` calls | `manager/request_manager/manager.py` (`AsyncAPIClient`) | Generic reusable async HTTP client wrapper (get/post/put/delete) with consistent `HTTPException` translation of `httpx` errors. |
| PostgreSQL (`get_db_connection`, used across `pto_logging*.py`, `pto_reporting.py`, `pto_feedback.py`, `pto_user_login_log.py`) | `services/azure/cosmosdb/manager.py` (`AzureCosmos`) + `models/tables.py` | Planned migration target per `project-improvements.md`. Implemented as a **singleton** async Cosmos DB client using `DefaultAzureCredential` (Managed Identity–compatible — addresses the "Managed Identity" and "singleton client" improvement items). Pydantic table models (`PTOLogging`, `UserLogging`) replace raw SQL row handling. |
| `calculate_vacation` (`pto_calculation.py`) request handler | `web/api/analytics/views.py` (`get_employee_details`) | Combines ERP fetch + Cosmos DB audit logging in one async endpoint, protected by JWT auth dependency; response modeled via `EmployeeResponseParsed`. |
| `process_document` (`pto_upload_file.py`) | `web/api/analytics/views.py` (`process_uploaded_document`) | **Stub only** — accepts `UploadFile`/form data but does not yet run OCR/LLM extraction (see gaps below). |
| Generic Flask error handling (per-route try/except) | `web/application.py` exception handlers + `middlewares/errors/handler.py` (`handle_exceptions` decorator) + `error_maps.py` | Global handlers for `HTTPException` and unhandled `Exception` return consistent JSON; a reusable decorator maps specific exception types (JWT, HTTP, timeout, etc.) to status codes — addresses the "detailed error handling" improvement item. |
| N/A | `/api/health` (monitoring), self-hosted Swagger/ReDoc (`/api/docs`, `/api/redoc`) | New capabilities not present in the Flask app. |

## 3. Not Yet Migrated (Gaps vs. Legacy Flask App)

These legacy modules have **no FastAPI equivalent yet**:

- **`pto_calculation2.py`** — LLM-based vacation policy extraction/formatting
  (`extract_vacation_section`, `format_data_using_llm`, markdown/newline
  cleanup helpers) used by the newer `/calculate_vacation_hours_new` route.
- **`pto_upload_file.py`** — actual OCR pipeline (`preprocess_image`,
  `extract_text_ocr_from_file` via Poppler/pdf2image + OCR) behind the
  `process_document` stub; today the analytics stub only echoes the filename.
- **`pto_reporting.py`** (`ReportService`, ~1000+ lines) — all `/api/v1/*`
  reporting endpoints: audit data, feedback data, combined audit data, unique
  states/employee IDs/usernames, counts, and CSV/export endpoints
  (`export_audit_date_range_state_filters`, `export_feedback_data_range_state_filters`).
- **`pto_logging_v2.py`** (`LoggingService`) — multi-stage PTO request logging
  (`post_initial_fields`, `patch_iteration_one`, `patch_iteration_two`),
  referenced in the legacy app as `/api/v2/*`. Only a single-shot Cosmos write
  exists today (`AzureCosmos.write_pto_logging`), not the patch/iteration flow.
- **`pto_feedback.py`** — feedback submission endpoint (`add_feedback`).
- **`pto_user_login_log.py`** — legacy standalone login-logging endpoint
  (superseded in part by the `write_user_logging` background task already
  wired into the SAML callback, but no equivalent direct endpoint/service
  layer exists).
- **`pto_logging.py`** — marked `# not used` in the legacy app; low priority.

## 4. Outstanding Items from `project-improvements.md`

- ✅ Client singleton pattern — done for Cosmos DB (`AzureCosmos.__new__`).
- ✅ Managed Identity–compatible init — done via `DefaultAzureCredential`.
- ✅ Cookie-based token storage — done (`HttpOnly` cookie in SAML ACS flow).
- ⏳ Database connection pooling — Cosmos SDK client is process-wide, but no
  explicit pool sizing/config yet.
- ⏳ Prompt caching / system prompt improvements for LLM calls — not
  applicable yet since the LLM-based `pto_calculation2.py` logic hasn't been
  ported.
- ⏳ Vector database for semantic search — not implemented (`azure-cosmos`
  is present as a dependency but only used for structured logging tables so
  far, not vector search).
- ⏳ Blob storage for uploaded documents — `process_uploaded_document` doesn't
  persist files anywhere yet (stub).
- ⏳ Securing reporting endpoints with token validation — moot until the
  reporting endpoints themselves are ported, but should be built in from the
  start using the existing `TokenGatewayManager.validate_token_entry_point`
  dependency.

## 5. Running the Project

```bash
uv sync --locked
uv run -m pto_backend         # dev server (honors PTO_BACKEND_RELOAD)
# or
docker compose up --build     # containerized dev server on :8000
```

Swagger UI: `http://localhost:8000/api/docs`
Health check: `GET /api/health`

Key environment variables (see `.env` / `pto_backend/settings.py`):
`TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`, `RESOURCE`, `TOKEN_URL`, `API_URL`
(ERP), `FRONTEND_URL`, `TOKEN_SECRET`, `TOKEN_AUDIENCE`, `COOKIE_DOMAIN`,
`COSMOS_DB_URL`, `COSMOS_DB_NAME`, plus standard `PTO_BACKEND_*` server
settings (`HOST`, `PORT`, `RELOAD`, `ENVIRONMENT`, `LOG_LEVEL`, `WORKERS_COUNT`).
