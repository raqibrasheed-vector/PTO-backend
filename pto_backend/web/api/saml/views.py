import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from pto_backend.manager.auth_validator.manager import TokenGatewayManager
from pto_backend.manager.auth_validator.schema import TokenSchema
from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.azure.cosmosdb.manager import AzureCosmos
from pto_backend.settings import settings
from pto_backend.web.api.saml import schema, utils
from pto_backend.web.enums.app_enums import AppCookieEnums
from pto_backend.web.types import common_types

router = APIRouter()


@router.post("/callback")
@handle_exceptions(re_raise=False, return_type=RedirectResponse)
async def handle_callback_saml(
    background_tasks: BackgroundTasks,
    saml_manager: utils.SAMLManager = Depends(utils.saml_function_wrapper),
    cosmos_client: AzureCosmos = Depends(),
) -> RedirectResponse:
    """
    Get SAML response for the application.
    """
    saml_response, username = await saml_manager.process_saml_request()

    # Adding backhtound task to set
    background_tasks.add_task(cosmos_client.write_user_logging, username)

    response = RedirectResponse(url=settings.frontend_url, status_code=303)

    response.set_cookie(
        key=AppCookieEnums.AccessToken.value,
        value=saml_response,
        httponly=True,
        secure=True,
        samesite="none",
        expires=datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(minutes=settings.access_token_expire_minutes),
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    return response


@router.post("/signout")
@handle_exceptions(re_raise=False, return_type=JSONResponse)
async def handle_user_logout() -> JSONResponse:

    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"isSignOut": True},
    )

    response.delete_cookie(
        key=AppCookieEnums.AccessToken.value,
        path="/",
        httponly=True,
        secure=True,
        samesite="none",
    )

    return response


@router.get("/login")
@handle_exceptions(re_raise=False, return_type=schema.SignInResponse)
async def create_login_request(
    saml_manager: utils.SAMLManager = Depends(utils.saml_function_wrapper),
) -> schema.SignInResponse:

    saml_login_url = await saml_manager.get_saml_login()

    return schema.SignInResponse(url=saml_login_url)


@router.get("/me")
@handle_exceptions(re_raise=False, return_type=common_types.CurrentUser)
async def get_current_user(
    current_user_data: TokenSchema = Depends(
        TokenGatewayManager.validate_token_entry_point
    ),
) -> common_types.CurrentUser:

    return common_types.CurrentUser(
        name=current_user_data.name,
        email=current_user_data.email,
        session_id=current_user_data.session_id,
        group=current_user_data.group,
    )


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> schema.Token:

    return schema.Token(access_token=form_data.password, token_type="bearer")
