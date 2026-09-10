from pydantic import BaseModel
from typing import Optional

class FeedBackResponse(BaseModel):
    feedback: Optional[str] = None
    feedback_type: Optional[str] = None
    pto_logging_id: str

class FiltersType(BaseModel):
    key: str
    value: str
    isSort: bool

class AuditDataResponse(BaseModel):
    employee_id: str
    start_date: str
    end_date:str
    created_at: str
    employee_name: str
    client_name: str
    total_hours: float
    total_leaves_used: float
    state: str
    leaves_available: float
    user_name: str
    file_name: Optional[str] = None
    feedback: Optional[str] = None
    feedback_type: Optional[str] = None
