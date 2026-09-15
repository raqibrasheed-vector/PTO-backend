import enum
import os
from pathlib import Path
from tempfile import gettempdir

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


TEMP_DIR = Path(gettempdir())


class LogLevel(enum.StrEnum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "0.0.0.0"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = True

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.DEBUG

    erp_tenant_id: str = os.getenv("TENANT_ID", "")
    erp_client_id: str = os.getenv("CLIENT_ID", "")
    erp_client_secret: str = os.getenv("CLIENT_SECRET", "")
    erp_resource: str = os.getenv("RESOURCE", "")
    erp_token_url: str = os.getenv("TOKEN_URL", "")
    erp_api_url: str = os.getenv("API_URL", "")

    frontend_url: str = os.getenv("FRONTEND_URL", "")
    saml_settings_base64: str = os.getenv("SAML_SETTINGS_BASE64", "")

    access_secret: str = os.getenv("TOKEN_SECRET", "")
    token_audience: str = os.getenv("TOKEN_AUDIENCE", "actalent")
    cookie_domain: str = os.getenv("COOKIE_DOMAIN", "")
    access_token_cookie_name: str = os.getenv(
        "ACCESS_TOKEN_COOKIE_NAME", "actalent_Token"
    )
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )
    session_token_cookie_name: str = os.getenv(
        "SESSION_TOKEN_COOKIE_NAME", "actalent_session"
    )

    cosmos_db_url: str = os.getenv("COSMOS_DB_URL", "")
    cosmos_db_name: str = os.getenv("COSMOS_DB_NAME", "")

    # Connection pool tuning for the shared async Cosmos DB HTTP transport.
    cosmos_pool_maxsize: int = int(os.getenv("COSMOS_POOL_MAXSIZE", "100"))
    cosmos_pool_maxsize_per_host: int = int(
        os.getenv("COSMOS_POOL_MAXSIZE_PER_HOST", "50")
    )
    cosmos_pool_keepalive_timeout: float = float(
        os.getenv("COSMOS_POOL_KEEPALIVE_TIMEOUT", "30")
    )
    cosmos_connection_timeout: int = int(os.getenv("COSMOS_CONNECTION_TIMEOUT", "5"))
    cosmos_request_timeout: int = int(os.getenv("COSMOS_REQUEST_TIMEOUT", "5"))

    # Document vectorization (semantic search over uploaded PTO documents).
    vectorstore_dir: str = os.getenv("VECTORSTORE_DIR", "vectorstores")
    vectorstore_ocr_dpi: int = int(os.getenv("VECTORSTORE_OCR_DPI", "300"))
    vectorstore_chunk_size: int = int(os.getenv("VECTORSTORE_CHUNK_SIZE", "2000"))
    vectorstore_chunk_overlap: int = int(os.getenv("VECTORSTORE_CHUNK_OVERLAP", "400"))
    vectorstore_default_query: str = os.getenv(
        "VECTORSTORE_DEFAULT_QUERY", "Vacation Policy"
    )
    vectorstore_default_top_k: int = int(os.getenv("VECTORSTORE_DEFAULT_TOP_K", "4"))

    # openAI configs
    open_ai_endpoint: str = os.getenv("OPENAI_ENDPOINT", "")
    open_ai_model_deployment: str = os.getenv("OPENAI_MODEL_DEPLOYMENT", "")
    open_ai_version: str = os.getenv("OPENAI_API_VERSION", "")
    open_ai_key: str = os.getenv("OPENAI_API_KEY", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PTO_BACKEND_",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
