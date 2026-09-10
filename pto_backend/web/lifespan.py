import base64
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from pto_backend.services.azure.cosmosdb.manager import AzureCosmos
from pto_backend.settings import settings


def create_saml_settings_file() -> None:
    """Decode the deployment SAML configuration into the local runtime path."""
    if not settings.saml_settings_base64:
        raise RuntimeError("SAML_SETTINGS_BASE64 must be configured")

    try:
        decoded = base64.b64decode(
            settings.saml_settings_base64, validate=True
        ).decode("utf-8")
        configuration = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("SAML_SETTINGS_BASE64 is not valid base64 JSON") from exc

    if not isinstance(configuration, dict):
        raise RuntimeError("SAML_SETTINGS_BASE64 must decode to a JSON object")

    saml_directory = Path(__file__).resolve().parent.parent / "saml"
    saml_directory.mkdir(parents=True, exist_ok=True)
    settings_path = saml_directory / "settings.json"
    temporary_path = settings_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(configuration, indent=2),
        encoding="utf-8",
    )
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, settings_path)


@asynccontextmanager
async def lifespan_setup(
    app: FastAPI,
) -> AsyncGenerator[None, None]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    in the state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    app.middleware_stack = None
    app.middleware_stack = app.build_middleware_stack()

    create_saml_settings_file()

    # Build the pooled Cosmos DB connection while the event loop is
    # already running, so requests reuse it instead of racing to create
    # it on first use.
    cosmos_client = AzureCosmos()
    await cosmos_client.initialize()

    yield

    await cosmos_client.close()
