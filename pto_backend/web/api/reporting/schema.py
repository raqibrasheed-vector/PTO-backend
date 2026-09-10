from pydantic import BaseModel, Field

from typing import Dict, List, Optional

from pto_backend.services.azure.cosmosdb.schema import FiltersType




class AuditDataRequest(BaseModel):
    limit: int = Field(default=20, gt=0, le=100)
    offset: int = Field(default=0, ge=0)
    filters: Optional[List[FiltersType]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


