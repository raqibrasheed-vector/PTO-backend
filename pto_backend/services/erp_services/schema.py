from typing import List

from pydantic import BaseModel, field_serializer, field_validator


class EmployeeResponse(BaseModel):
    customer_id: str
    customer_name: str
    employee_id: str
    employee_name: str
    home_state: str
    job_req_status: str
    regular_hours_worked: float
    remote_worker: str
    state: str
    used_vacations: float


class EmployeeResponseParsed(BaseModel):
    id: str
    employee_list: List[EmployeeResponse]

   

    # @field_serializer("employee_name")
    # def serialize_employee_name(self, value: str) -> str:
    #     if not value:
    #         return value

    #     if "," in value:
    #         last_name, first_name = value.split(",", 1)
    #         return f"{first_name.strip()}, {last_name.strip()}"

    #     return value.strip()
