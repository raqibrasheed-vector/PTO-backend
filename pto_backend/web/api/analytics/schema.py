from typing import Dict, List

from pydantic import BaseModel

from pto_backend.services.vectorization.schema import DocumentChunk


class GetEmployeeDetails(BaseModel):
    employee_id: str
    start_date: str
    end_date: str


class ProcessDocumentResponse(BaseModel):
    employee_id: str
    file_name: str
    query: str
    pto_logging_id: str | None = None
    results: list[DocumentChunk]


class CalculateVacations(BaseModel):
    start_date: str
    end_date: str
    regular_hours_worked: float
    state: str
    client_name: str
    used_vacations: str
    text_inputs: List[Dict[str,str]]
    pto_logging_id: str

class FeedBackFormSubmit(BaseModel):
    pto_logging_id: str
    feedback: str
    feedback_type: str
    file_name: str
    employee_id: str
    start_date: str
    end_date: str
    employee_name: str
    client_name: str
    total_hours: float
    total_leaves_used: float
    state: str
    leaves_available: float