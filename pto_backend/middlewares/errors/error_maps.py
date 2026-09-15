import httpx
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
    TimeoutError: (
        status.HTTP_504_GATEWAY_TIMEOUT,
        "The external service timed out. Please try again later.",
    ),
    ConnectionError: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The external service is unavailable. Please try again later.",
    ),
    httpx.HTTPStatusError: (
        status.HTTP_502_BAD_GATEWAY,
        "The external service is unavailable. Please try again later.",
    ),
    httpx.TimeoutException: (
        status.HTTP_504_GATEWAY_TIMEOUT,
        "The external service timed out. Please try again later.",
    ),
    httpx.RequestError: (
        status.HTTP_502_BAD_GATEWAY,
        "The external service is unavailable. Please try again later.",
    ),
    ReadTimeout: (status.HTTP_408_REQUEST_TIMEOUT, "Request timeout."),
    jwt.ExpiredSignatureError: (status.HTTP_401_UNAUTHORIZED, "Token Expired"),
    jwt.InvalidTokenError: (status.HTTP_400_BAD_REQUEST, "Invalid Token"),
}
