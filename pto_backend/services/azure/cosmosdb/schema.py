from pydantic import BaseModel


class FeedBackResponse(BaseModel):
    feedback: str | None = None
    feedback_type: str | None = None
    pto_logging_id: str


class FiltersType(BaseModel):
    key: str
    value: str
    isSort: bool


class AuditDataResponse(BaseModel):
    employee_id: str
    start_date: str
    end_date: str
    created_at: str
    employee_name: str
    client_name: str
    total_hours: float
    total_leaves_used: float
    state: str
    leaves_available: float
    user_name: str
    file_name: str | None = None
    feedback: str | None = None
    feedback_type: str | None = None
