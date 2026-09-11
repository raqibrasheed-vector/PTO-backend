from datetime import datetime
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook

from pto_backend.manager.auth_validator.manager import TokenGatewayManager
from pto_backend.manager.auth_validator.schema import TokenSchema
from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.azure.cosmosdb.manager import AuditDataResponse, AzureCosmos
from pto_backend.types.api_types import PaginationResponse
from pto_backend.web.api.reporting import schema

router = APIRouter()

EXPORT_COLUMNS = [
    "employee_id",
    "start_date",
    "end_date",
    "employee_name",
    "client_name",
    "total_hours",
    "total_leaves_used",
    "state",
    "leaves_available",
    "created_at",
    "user_name",
    "file_name",
    "feedback",
    "feedback_type",
]


def format_export_date(value: object) -> object:
    if not isinstance(value, str) or not value:
        return value

    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).strftime("%m/%d/%Y")
    except ValueError:
        return value


def create_xlsx_response(
    records: list[AuditDataResponse], filename: str
) -> StreamingResponse:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Report"
    worksheet.append([column.upper() for column in EXPORT_COLUMNS])

    for record in records:
        row = []
        for column in EXPORT_COLUMNS:
            value = getattr(record, column, None)
            if column in {"start_date", "end_date", "created_at"}:
                value = format_export_date(value)
            if column == "feedback_type":
                if isinstance(value, str):
                    value = {
                        "thumbs_up": "Positive",
                        "thumbs_down": "Negative",
                    }.get(value, value)
            row.append(value)
        worksheet.append(row)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/table-filters")
@handle_exceptions(re_raise=False, return_type=JSONResponse)
async def get_table_filters(
    filter_data: Literal["audit", "feedback"],
    cosmos_client: AzureCosmos = Depends(),
    _: TokenSchema = Depends(TokenGatewayManager.validate_token_entry_point_admin),
) -> JSONResponse:

    table_data = await cosmos_client.get_pto_logging_table_data_filters()

    return JSONResponse(content=table_data)


@router.post("/audit-data")
@handle_exceptions(
    re_raise=False,
    return_type=PaginationResponse[list[AuditDataResponse]],
)
async def get_audit_data(
    filter_data: schema.AuditDataRequest,
    cosmos_client: AzureCosmos = Depends(),
    _: TokenSchema = Depends(TokenGatewayManager.validate_token_entry_point_admin),
) -> PaginationResponse[list[AuditDataResponse]]:

    audit_response_data, pagination = await cosmos_client.get_audit_data(
        **filter_data.model_dump()
    )

    return PaginationResponse(data=audit_response_data, **pagination.model_dump())


@router.post("/audit-export")
@handle_exceptions(re_raise=False, return_type=StreamingResponse)
async def export_audit_data(
    filter_data: schema.AuditDataRequest,
    cosmos_client: AzureCosmos = Depends(),
    _: TokenSchema = Depends(TokenGatewayManager.validate_token_entry_point_admin),
) -> StreamingResponse:
    records = await cosmos_client.get_audit_data_for_export(
        filters=filter_data.filters,
        start_date=filter_data.start_date,
        end_date=filter_data.end_date,
    )

    return create_xlsx_response(records, "audit-report.xlsx")


@router.post("/feedback-data")
@handle_exceptions(
    re_raise=False,
    return_type=PaginationResponse[list[AuditDataResponse]],
)
async def get_feedback_data(
    filter_data: schema.AuditDataRequest,
    cosmos_client: AzureCosmos = Depends(),
    _: TokenSchema = Depends(TokenGatewayManager.validate_token_entry_point_admin),
) -> PaginationResponse[list[AuditDataResponse]]:
    feedback_data, pagination = await cosmos_client.get_feedback_data(
        **filter_data.model_dump()
    )
    return PaginationResponse(data=feedback_data, **pagination.model_dump())


@router.post("/feedback-export")
@handle_exceptions(re_raise=False, return_type=StreamingResponse)
async def export_feedback_data(
    filter_data: schema.AuditDataRequest,
    cosmos_client: AzureCosmos = Depends(),
    _: TokenSchema = Depends(TokenGatewayManager.validate_token_entry_point_admin),
) -> StreamingResponse:
    records = await cosmos_client.get_feedback_data_for_export(
        filters=filter_data.filters,
        start_date=filter_data.start_date,
        end_date=filter_data.end_date,
    )
    return create_xlsx_response(records, "feedback-report.xlsx")
