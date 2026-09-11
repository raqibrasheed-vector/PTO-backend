from typing import Any

from async_lru import alru_cache
from fastapi import HTTPException

from pto_backend.manager.request_manager.manager import AsyncAPIClient
from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.erp_services import schema
from pto_backend.settings import settings


def _required_text(employee: dict[str, Any], field: str) -> str:
    value = employee.get(field)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=502,
            detail=f"ERP response is missing a valid {field} value",
        )
    return value


def _required_number(employee: dict[str, Any], field: str) -> float:
    value = employee.get(field)
    if not isinstance(value, (int, float, str)):
        raise HTTPException(
            status_code=502,
            detail=f"ERP response is missing a valid {field} value",
        )
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"ERP response is missing a valid {field} value",
        ) from exc


class ErpServicesManager:
    """Class to handle all the ERP manager requests and data"""

    def __init__(self) -> None:
        self.requestSession = AsyncAPIClient(url=settings.erp_api_url)

    @alru_cache(ttl=1800)
    async def __get_erp_token(self) -> str:
        """Function to get the erp access token for the api requests"""
        token_url = (
            settings.erp_token_url.split("{")[0]
            + settings.erp_tenant_id
            + settings.erp_token_url.split("}")[1]
        )

        # Initialize the API Request for token url
        api_manager = AsyncAPIClient(url=token_url)

        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.erp_client_id,
            "client_secret": settings.erp_client_secret,
            "resource": settings.erp_resource,
        }

        try:
            token_data = await api_manager.post(endpoint="/oauth2/token", data=payload)

            token = token_data.get("access_token")
            if not isinstance(token, str) or not token:
                raise HTTPException(status_code=400, detail="Token response is invalid")
        finally:
            await api_manager.close()

        return token

    @handle_exceptions(re_raise=True, return_type=list[schema.EmployeeResponse])
    async def fetch_employee_details(
        self, employee_id: str, start_date: str, end_date: str
    ) -> list[schema.EmployeeResponse]:

        params = {
            "EmployeeId": employee_id,
            "StartDate": start_date,
            "EndDate": end_date,
        }

        headers = {
            "Authorization": f"Bearer {await self.__get_erp_token()}",
            "Content-Type": "application/json",
        }

        try:
            employee_data = await self.requestSession.get(
                endpoint="/allegis-prod-psemployeetimedataapi/v1/timecode/summary",
                params=params,
                headers=headers,
            )

            if not isinstance(employee_data, list) or not employee_data:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Employee details not found. Please verify the Employee ID "
                        "and try again."
                    ),
                )

            employee_list: list[schema.EmployeeResponse] = [
                schema.EmployeeResponse(
                    employee_id=_required_text(selected_employee, "EmployeeId"),
                    employee_name=_required_text(selected_employee, "EmployeeName"),
                    used_vacations=_required_number(
                        selected_employee, "TotalHrsVacUsed"
                    ),
                    regular_hours_worked=_required_number(
                        selected_employee, "TotalHrsWorked"
                    ),
                    state=_required_text(selected_employee, "State"),
                    customer_name=_required_text(selected_employee, "CustomerName"),
                    customer_id=_required_text(selected_employee, "CustomerId"),
                    remote_worker=_required_text(selected_employee, "RemoteWorker"),
                    home_state=_required_text(selected_employee, "HomeState"),
                    job_req_status=_required_text(selected_employee, "JobReqStatus"),
                )
                for selected_employee in employee_data
                if isinstance(selected_employee, dict)
            ]

            employee_list = sorted(employee_list, key=lambda x: x.job_req_status)

            return employee_list
        finally:
            await self.requestSession.close()
