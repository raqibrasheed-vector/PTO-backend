# Copilot Instructions for `pto_backend`

## What this is

FastAPI rewrite of a legacy Flask PTO application (`../PTO-Backend`). See
`PROJECT_OVERVIEW.md` for the full legacy-vs-new mapping table and the list
of legacy modules not yet ported (reporting endpoints, `pto_logging_v2`
patch/iteration flow, feedback endpoints, etc.) — check it before assuming a
feature doesn't exist yet.

## Commands

Package manager is `uv` (not pip/poetry directly).

```bash
uv sync --locked              # install deps (add --all-groups for dev+test tools)
uv run -m pto_backend         # run dev server (honors PTO_BACKEND_RELOAD/PORT/HOST)
docker compose up --build     # containerized dev server on :8000, autoreload, volume-mounted
```

Tests (pytest + anyio, async tests use `client`/`fastapi_app` fixtures from `tests/conftest.py`):

```bash
uv run pytest -vv .                              # full suite
uv run pytest -vv tests/test_pto_backend.py       # single file
uv run pytest -vv tests/test_pto_backend.py::test_health   # single test
```

Lint/type-check (also runs via `pre-commit install`, see `.pre-commit-config.yaml`):

```bash
uv run ruff format
uv run ruff check pto_backend tests --fix
uv run mypy pto_backend tests
```

Ruff config lives in `pyproject.toml` (`target-version = py313`, line-length 88,
`strict` mypy). Run against just the file(s) you touched when iterating, e.g.
`uv run ruff check pto_backend/web/api/analytics/views.py`.

## Architecture

Request flow: `web/api/router.py` aggregates sub-routers (`monitoring`, `docs`,
`saml`, `analytics`) under the `/api` prefix from `web/application.py`. Each
feature package under `web/api/<name>/` follows the same shape:
`views.py` (route handlers), `schema.py` (Pydantic request/response models),
and sometimes `utils.py` for FastAPI dependency wrappers (e.g.
`saml/utils.py:saml_function_wrapper`).

Business logic lives outside `web/`, under `manager/` (cross-cutting:
auth/JWT, SAML, generic HTTP client) and `services/` (external integrations:
Cosmos DB, ERP API, Azure OpenAI/foundry chat, document vectorization).
Routes stay thin — they call into a manager/service class injected via
`Depends()` and translate results into response schemas.

**Two different "manager" instantiation patterns coexist — check before
copying a pattern:**
- **Singletons** (`AzureCosmos`, `VectorizationManager`,
  `AzureVacationChatClient`): implement `__new__` + an `_initialized` guard
  in `__init__` so `Depends(SomeManager)` always resolves to the same
  process-wide instance (shared connection pool / loaded ML model). Cosmos
  additionally lazy-inits its client (`initialize()`, idempotent, called both
  from `web/lifespan.py` startup and defensively from each method).
- **Plain per-request instances** (`ErpServicesManager`,
  `TokenGatewayManager`, `AsyncAPIClient`): no singleton guard, a fresh
  instance is constructed per `Depends()` call.

Startup/shutdown hooks (building the pooled Cosmos client, closing it) live
in `web/lifespan.py`, wired into the app via `lifespan=lifespan_setup` in
`web/application.py`.

## Key conventions

**Error handling** — every route handler and every "outer" manager/service
method that's called directly from a route body should be wrapped with
`@handle_exceptions` from `middlewares/errors/handler.py`:
- Route handlers: `@handle_exceptions(re_raise=False, return_type=<ResponseModel>)`
  — converts exceptions to an `HTTPException` using `middlewares/errors/error_maps.py`'s
  `error_mappings` (falls back to 500 for unmapped types). `return_type` is
  documentation-only (unused at runtime) but should still match the route's
  actual response model.
- Manager/service methods called in-body from a route: `@handle_exceptions(re_raise=True)`
  — logs the exception then re-raises it unchanged so the *outer* route
  decorator performs the actual HTTP conversion. Don't decorate both a
  method and every function that calls it — decorate the outermost
  service-layer entry point only (e.g. `AzureCosmos.write_pto_logging`, not
  its private helpers).
- Don't decorate FastAPI `Depends()`-injected dependency functions (e.g.
  `TokenGatewayManager.validate_token_entry_point`) expecting the route's
  decorator to catch them — dependencies are resolved by FastAPI before the
  route body runs, so their exceptions never pass through the route's
  try/except. Such dependencies should handle/convert their own errors.
- Skip lifecycle methods called from `web/lifespan.py` (`initialize`,
  `close`, `ensure_containers_initialization`) — not per-request business
  logic.

**Settings** (`pto_backend/settings.py`) — mixes two conventions:
`PTO_BACKEND_`-prefixed fields use pydantic-settings' normal env-loading
(`host`, `port`, `reload`, `environment`, `log_level`). Everything else
(ERP/SAML/Cosmos/OpenAI config) reads unprefixed vars directly via
`os.getenv(...)` as field defaults, for compatibility with the legacy
Flask app's `.env` file. When adding a new setting, match whichever group
it conceptually belongs to.

**Singleton managers as FastAPI dependencies** — routes take
`manager: SomeManager = Depends()` (bare `Depends()`, not
`Depends(get_some_manager)`) relying on `SomeManager()` being cheap/idempotent
to construct.

**Vectorization** (`services/vectorization/manager.py`) — CPU-only stack by
design: PyMuPDF (not `pdf2image`/Poppler) for PDF rasterization, FastEmbed
(ONNX) for embeddings (not sentence-transformers/torch), FAISS's own
`save_local`/`load_local` (not raw `pickle`) since the embedding backend
generally isn't picklable. Blocking work (parsing/OCR/embedding/FAISS) is
pushed off the event loop via `asyncio.to_thread`. Per-employee vectorstores
are persisted under `<vectorstore_dir>/<employee_id>/`.

**Logging** — two independent loggers exist: `loguru` via `log.py`
(intercepts stdlib/uvicorn logging, configured in `configure_logging()`) for
general app logs, and a separate colorized singleton
(`middlewares/customlogger/customlogger.py:SingletonLogger`) used
specifically by the `handle_exceptions` decorator. Don't conflate the two.
