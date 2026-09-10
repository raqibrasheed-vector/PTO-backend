import jwt
from fastapi import status
from requests.exceptions import HTTPError, ReadTimeout  # type: ignore

error_mappings = {
    ZeroDivisionError: (
        status.HTTP_400_BAD_REQUEST,
        "Division by zero is not allowed.",
    ),
    IndentationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error."),
    ValueError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "server error"),
    HTTPError: (status.HTTP_400_BAD_REQUEST, "server error"),
    ReadTimeout: (status.HTTP_408_REQUEST_TIMEOUT, "Request timeout."),
    jwt.ExpiredSignatureError: (status.HTTP_401_UNAUTHORIZED, "Token Expired"),
    jwt.InvalidTokenError: (status.HTTP_400_BAD_REQUEST, "Invalid Token"),
}
