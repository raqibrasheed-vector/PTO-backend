from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pto_backend.log import configure_logging
from pto_backend.settings import settings
from pto_backend.web.api.router import api_router
from pto_backend.web.lifespan import lifespan_setup
from pto_backend.web.api.saml import router

APP_ROOT = Path(__file__).parent.parent


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    :return: FastAPI application.
    """
    configure_logging()

    app = FastAPI(
        title="pto_backend",
        lifespan=lifespan_setup,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # Function to handle HTTP Exception
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # Function to handle generic exception
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong. Please try again."},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url] if settings.frontend_url else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router=router, prefix="/saml", tags=["SAML Authentications"])

    app.include_router(
        router=api_router,
        prefix="/api",
    )

    app.mount(
        "/static",
        StaticFiles(directory=APP_ROOT / "static"),
        name="static",
    )

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        # Make UploadFile compatible with Swagger UI's
        # traditional file input representation.
        for component in schema.get("components", {}).get("schemas", {}).values():
            for prop in component.get("properties", {}).values():
                if prop.get("contentMediaType") == "application/octet-stream":
                    prop.pop("contentMediaType", None)
                    prop["format"] = "binary"

        app.openapi_schema = schema

        return schema

    app.openapi = custom_openapi  # type: ignore

    return app
