
from async_lru import alru_cache
from fastapi import HTTPException

from pto_backend.manager.request_manager.manager import AsyncAPIClient
from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.erp_services import schema
from pto_backend.settings import settings


class ErpServicesManager:
    """Class to handle all the ERP manager requests and data"""

    def __init__(self):
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
        finally:
            await api_manager.close()

        return token_data.get("access_token")

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
            employee_Data: list[dict[str, str]] = await self.requestSession.get(
                endpoint="/allegis-prod-psemployeetimedataapi/v1/timecode/summary",
                params=params,
                headers=headers,
            )

            if not employee_Data:
                raise HTTPException(
                    status_code=404,
                    detail="Employee details not found. Please verify the Employee ID and try again.",
                )

            employee_list: list[schema.EmployeeResponse] = [
                schema.EmployeeResponse(
                    employee_id=selected_employee.get("EmployeeId"),
                    employee_name=selected_employee.get("EmployeeName"),
                    used_vacations=selected_employee.get("TotalHrsVacUsed"),
                    regular_hours_worked=selected_employee.get("TotalHrsWorked"),
                    state=selected_employee.get("State"),
                    customer_name=selected_employee.get("CustomerName"),
                    customer_id=selected_employee.get("CustomerId"),
                    remote_worker=selected_employee.get("RemoteWorker"),
                    home_state=selected_employee.get("HomeState"),
                    job_req_status=selected_employee.get("JobReqStatus"),
                )
                for selected_employee in employee_Data
            ]

            employee_list = sorted(employee_list, key=lambda x: x.job_req_status)

            return employee_list
        finally:
            await self.requestSession.close()
