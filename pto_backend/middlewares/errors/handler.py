from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from fastapi import status
from fastapi.exceptions import HTTPException

from pto_backend.middlewares.customlogger.customlogger import SingletonLogger
from pto_backend.middlewares.errors.error_maps import error_mappings

logger = SingletonLogger().get_logger()

T = TypeVar("T")
P = ParamSpec("P")


def _get_error_response(
    error: Exception,
    exception_map: dict[type[Exception], tuple[int, str]] | None,
    default_status_code: int,
    default_message: str,
) -> tuple[int, str]:
    if not exception_map:
        return default_status_code, default_message

    mapped_response = exception_map.get(type(error))
    if mapped_response:
        return mapped_response

    for exception_type, response in exception_map.items():
        if isinstance(error, exception_type):
            return response

    return default_status_code, default_message


def handle_exceptions(
    exception_map: dict[type[Exception], tuple[int, str]] | None = error_mappings,
    log_func: Callable[[str], None] | None = None,
    re_raise: bool = False,
    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    default_message: str = "Something went wrong. Please try again.",
    return_type: type[T] | tuple[type[T], ...] | None = None,
) -> Callable[
    [Callable[P, T | Awaitable[T]]],
    Callable[P, Awaitable[T]],
]:
    """
    A decorator to handle custom exceptions in both sync and async functions.
    Args:
        custom_exceptions: A tuple of exceptions to catch.
        log_func: A function to log errors.
        re_raise: Whether to re-raise the caught exception after handling it.
        default_return: The default value to return when an exception is caught.
    Returns:
        The wrapped function with exception handling.
    """

    def decorator(
        func: Callable[P, T | Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                result = func(*args, **kwargs)
                return await result if isinstance(result, Awaitable) else result
            except Exception as e:
                logger.critical(f"HTTP exception: {e,type(e)}")
                if re_raise:
                    raise
                status_code, message = _get_error_response(
                    e,
                    exception_map,
                    default_status_code,
                    default_message,
                )
                if type(e) is HTTPException:
                    raise HTTPException(status_code=e.status_code, detail=e.detail)

                if log_func:
                    log_func(message)
                raise HTTPException(status_code=status_code, detail=message)

        return async_wrapper

    return decorator
