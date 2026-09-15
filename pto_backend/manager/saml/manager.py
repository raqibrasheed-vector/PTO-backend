from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from pto_backend.manager.auth_validator.manager import TokenGatewayManager
from pto_backend.manager.saml import schema
from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.settings import settings

# List of claim attributes
EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"

DISPLAY_NAME_CLAIM = "http://schemas.microsoft.com/identity/claims/displayname"

OBJECT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"

GROUPS_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"


class SAMLManager:
    """Manager class to handle all the saml and auth mechanisms"""

    def __init__(self, request: Request):

        # get the saml metadata file path
        BASE_DIR = Path(__file__).resolve().parent.parent.parent

        self.request_data = request
        self.saml_path = BASE_DIR / "saml"

        self.token_manager = TokenGatewayManager()

    async def prepare_saml_request(self) -> schema.SAMLResponse:

        scheme = self.request_data.url.scheme

        forwarded_proto = self.request_data.headers.get("x-forwarded-proto")

        if forwarded_proto:
            scheme = forwarded_proto.split(",")[0].strip()

        host = self.request_data.headers.get("host", self.request_data.url.netloc)

        return schema.SAMLResponse(
            https="on" if scheme == "https" else "off",
            http_host=host,
            server_port=("443" if scheme == "https" else "80"),
            script_name="",
            get_data=dict(self.request_data.query_params),
            post_data={},
            query_string=self.request_data.url.query,
        )

    @handle_exceptions(re_raise=True, return_type=str)
    async def get_saml_login(self) -> str | Any:

        saml_response = await self.prepare_saml_request()

        auth_login = OneLogin_Saml2_Auth(
            saml_response, custom_base_path=str(self.saml_path)
        )

        return auth_login.login(return_to=settings.frontend_url)

    async def flattern_arrtibutes(self, saml_data: dict[str, Any]) -> dict[str, str]:
        flat_attributes = {
            key: str(values[0]) if values else "" for key, values in saml_data.items()
        }
        return flat_attributes

    @handle_exceptions(re_raise=True, return_type=tuple)
    async def process_saml_request(self) -> tuple[str, str]:
        form = await self.request_data.form()

        saml_response = form.get("SAMLResponse")

        if not isinstance(saml_response, str) or not saml_response:
            raise HTTPException(status_code=400, detail="Missing SAMLResponse")

        saml_request = await self.prepare_saml_request()

        saml_request_data = saml_request.model_dump()

        saml_request_data["post_data"] = {"SAMLResponse": saml_response}

        relay_state = form.get("RelayState")

        if relay_state:
            saml_request_data["post_data"]["RelayState"] = str(relay_state)

        auth = OneLogin_Saml2_Auth(
            saml_request_data, custom_base_path=str(self.saml_path)
        )

        try:
            auth.process_response()
        except Exception as exc:
            raise HTTPException(
                status_code=401, detail=f"SAML processing failed: {exc}"
            )

        errors = auth.get_errors()

        if errors:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "SAML validation failed",
                    "errors": errors,
                    "reason": auth.get_last_error_reason(),
                },
            )

        attributes = await self.flattern_arrtibutes(auth.get_attributes())

        required_attributes = {
            "email": attributes.get(EMAIL_CLAIM, ""),
            "display name": attributes.get(DISPLAY_NAME_CLAIM, ""),
            "group": attributes.get(GROUPS_CLAIM, ""),
        }
        missing_attributes = [
            name for name, value in required_attributes.items() if not value.strip()
        ]

        if missing_attributes:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Required SAML attributes are missing",
                    "attributes": missing_attributes,
                },
            )

        email = required_attributes["email"]
        display_name = required_attributes["display name"]
        group_name = required_attributes["group"]

        access_token = await self.token_manager.generate_login_tokens(
            email=email, name=display_name, group=group_name, session_id=uuid4()
        )

        return access_token, display_name
