from fastapi.routing import APIRouter

from pto_backend.web.api import analytics, docs, monitoring, reporting, saml

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(docs.router)
api_router.include_router(saml.router, prefix="/saml", tags=["SAML"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["AI Analytics"])
api_router.include_router(
    reporting.router, prefix="/reporting", tags=["Reporting Services"]
)
