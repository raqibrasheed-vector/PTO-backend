from pydantic import BaseModel, Field

from pto_backend.services.azure.cosmosdb.schema import FiltersType


class AuditDataRequest(BaseModel):
    limit: int = Field(default=20, gt=0, le=100)
    offset: int = Field(default=0, ge=0)
    filters: list[FiltersType] | None = None
    start_date: str | None = None
    end_date: str | None = None
