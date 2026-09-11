from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from pto_backend.manager.auth_validator.manager import TokenGatewayManager
from pto_backend.manager.auth_validator.schema import TokenSchema
from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.azure.cosmosdb.manager import AzureCosmos, tables
from pto_backend.services.azure.foundry.ai_client import AzureVacationChatClient
from pto_backend.services.azure.foundry.response_types.llm_responses import (
    PTOSummariserParser,
)
from pto_backend.services.erp_services.manager import (
    ErpServicesManager,
)
from pto_backend.services.erp_services.manager import (
    schema as erp_schema,
)
from pto_backend.services.vectorization.manager import (
    UnsupportedFileTypeError,
    VectorizationManager,
)
from pto_backend.web.api.analytics import schema

# Initialize the FastApi Analytics routes
router = APIRouter()


@router.post("/process-document", response_model=schema.ProcessDocumentResponse)
@handle_exceptions(re_raise=False, return_type=schema.ProcessDocumentResponse)
async def process_uploaded_document(
    file: UploadFile,
    employee_id: Annotated[str, Form()],
    pto_logging_id: Annotated[str, Form()],
    client_name: Annotated[str, Form()],
    query: Annotated[str | None, Form()] = None,
    vector_manager: VectorizationManager = Depends(),
    cosmos_client: AzureCosmos = Depends(),
    current_user_data: TokenSchema = Depends(
        TokenGatewayManager.validate_token_entry_point
    ),
) -> schema.ProcessDocumentResponse:
    """
    Vectorize an uploaded PTO document (PDF/DOCX) and run a semantic search
    against it (defaults to the "Vacation Policy" query, same as legacy).

    If ``pto_logging_id`` is supplied (the id returned by
    ``/employee-details``), the matching Cosmos DB audit entry is patched
    with the processed file's name.
    """
    file_bytes = await file.read()

    try:
        vectorization_result = await vector_manager.process_document(
            file_bytes=file_bytes,
            filename=file.filename or "",
            employee_id=employee_id,
            query=query,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if pto_logging_id:
        await cosmos_client.update_pto_logging(
            pto_logging_id=pto_logging_id,
            username=current_user_data.name,
            file_name=vectorization_result.file_name,
            client_name=client_name,
        )

    return schema.ProcessDocumentResponse(
        employee_id=vectorization_result.employee_id,
        file_name=vectorization_result.file_name,
        query=vectorization_result.query,
        pto_logging_id=pto_logging_id,
        results=vectorization_result.results,
    )


@router.post("/employee-details", response_model=erp_schema.EmployeeResponseParsed)
@handle_exceptions(re_raise=False, return_type=erp_schema.EmployeeResponseParsed)
async def get_employee_details(
    employee_data: schema.GetEmployeeDetails,
    erp_manager: ErpServicesManager = Depends(),
    cosmos_client: AzureCosmos = Depends(),
    current_user_data: TokenSchema = Depends(
        TokenGatewayManager.validate_token_entry_point
    ),
) -> erp_schema.EmployeeResponseParsed:

    get_employee_data = await erp_manager.fetch_employee_details(
        **employee_data.model_dump()
    )

    current_employee = next(iter(get_employee_data))

    pto_logging = await cosmos_client.write_pto_logging(
        pto_data=tables.PTOLogging(
            user_name=current_user_data.name,
            employee_id=current_employee.employee_id,
            session_id=current_user_data.session_id,
            start_date=employee_data.start_date,
            end_date=employee_data.end_date,
            employee_name=current_employee.employee_name,
            client_name=current_employee.customer_name,
            total_hours=current_employee.regular_hours_worked,
            total_leaves_used=current_employee.used_vacations,
            state=current_employee.state,
            leaves_available=0,
            file_name="",
        )
    )

    return erp_schema.EmployeeResponseParsed(
        id=str(pto_logging), employee_list=get_employee_data
    )


@router.post("/calculate-vacation", response_model=PTOSummariserParser)
@handle_exceptions(re_raise=False, return_type=PTOSummariserParser)
async def calculate_available_vacation(
    employee_meta: schema.CalculateVacations,
    azure_openai_client: AzureVacationChatClient = Depends(),
    cosmos_client: AzureCosmos = Depends(),
    current_user_data: TokenSchema = Depends(
        TokenGatewayManager.validate_token_entry_point
    ),
) -> PTOSummariserParser:

    pto_calculation = await azure_openai_client.calculate_vacation(
        **employee_meta.model_dump(
            exclude={
                "pto_logging_id",
                "client_name",
            }
        )
    )

    await cosmos_client.update_pto_logging(
        pto_logging_id=employee_meta.pto_logging_id,
        username=current_user_data.name,
        leaves_available=pto_calculation.vacation_hours_available,
        client_name=employee_meta.client_name,
    )

    return pto_calculation


@router.post("/submit-feedback", response_model=schema.FeedBackFormSubmit)
@handle_exceptions(re_raise=False, return_type=schema.FeedBackFormSubmit)
async def submit_analytics_feedback(
    feedback_data: schema.FeedBackFormSubmit,
    cosmos_client: AzureCosmos = Depends(),
    current_user: TokenSchema = Depends(TokenGatewayManager.validate_token_entry_point),
) -> schema.FeedBackFormSubmit:

    await cosmos_client.write_pto_feedback(
        pto_data=tables.PTOFeedBackForm(
            **feedback_data.model_dump(),
            user_name=current_user.name,
            session_id=current_user.session_id,
        ),
    )

    return feedback_data
