import datetime
from typing import Annotated, TypeVar
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import exceptions as jwt_exc

from pto_backend.manager.auth_validator.schema import TokenSchema
from pto_backend.settings import settings
from pto_backend.web.enums.app_enums import AppCookieEnums

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/saml/token", auto_error=False)

T = TypeVar("T")


class TokenExpiredException(Exception):
    """Custom exception for expired tokens."""


class UnauthorizedException(Exception):
    """Custom exception for expired tokens."""


class TokenGatewayManager:
    """Class to manage all the incoming network traffic."""

    def __init__(self) -> None:
        self.access_secret: str = settings.access_secret
        self.token_audience: str = settings.token_audience

    async def generate_login_tokens(
        self, email: str, name: str, session_id: UUID, group: str
    ) -> str:
        """
        Generate both access and refresh JWT tokens for a user.
        """

        now = datetime.datetime.utcnow()

        # Access token (short-lived)
        access_payload = TokenSchema(
            email=email,
            iat=now,
            exp=now + datetime.timedelta(minutes=500),
            name=name,
            aud=self.token_audience,
            session_id=str(session_id),
            group=group,
        )
        access_token = jwt.encode(
            access_payload.model_dump(), self.access_secret, algorithm="HS256"
        )

        return access_token

    async def verify_token(self, token: str) -> TokenSchema:
        """
        Verify and decode a JWT token.
        """

        decoded = jwt.decode(
            token,
            self.access_secret,
            algorithms=["HS256"],
            audience=self.token_audience,
        )

        return TokenSchema(**decoded)

    @staticmethod
    async def validate_token_entry_point(
        request: Request,
        token: Annotated[str, Depends(oauth2_scheme)],  # from Authorization header
    ) -> TokenSchema:
        try:
            # Prefer cookie token if available, else fall back to header token
            cookie_token = request.cookies.get(AppCookieEnums.AccessToken.value)

            final_token = cookie_token or token

            token_verifier = TokenGatewayManager()

            if not final_token:
                raise TokenExpiredException

            token_data = await token_verifier.verify_token(token=final_token)

            return token_data
        except TokenExpiredException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid token found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.DecodeError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as err:
            print(">>>>", err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing the token",
            )

    @staticmethod
    async def validate_token_entry_point_admin(
        request: Request,
        token: Annotated[str, Depends(oauth2_scheme)],  # from Authorization header
    ) -> TokenSchema:
        try:
            # Prefer cookie token if available, else fall back to header token
            cookie_token = request.cookies.get(AppCookieEnums.AccessToken.value)

            final_token = cookie_token or token

            token_verifier = TokenGatewayManager()

            if not final_token:
                raise TokenExpiredException

            token_data = await token_verifier.verify_token(token=final_token)

            if token_data.group != "admin":
                raise UnauthorizedException

            return token_data
        except UnauthorizedException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except TokenExpiredException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid token found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.DecodeError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt_exc.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as err:
            print(">>>>", err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing the token",
            )
