from typing import Any

import httpx
from fastapi import HTTPException


class AsyncAPIClient:
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 10,
    ):
        self.base_url = url
        self.default_headers = headers or {}
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request("GET", endpoint, params=params, headers=headers)

    async def post(
        self,
        endpoint: str,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            endpoint,
            data=data,
            json=json,
            headers=headers,
        )

    async def put(
        self,
        endpoint: str,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            endpoint,
            data=data,
            json=json,
            headers=headers,
        )

    async def delete(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        return await self._request("DELETE", endpoint, headers=headers)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] = {},
        json: dict[str, Any] = {},
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        merged_headers = {**self.default_headers, **(headers or {})}
        merged_params = {**(params or {})}

        try:
            response = await self.client.request(
                method,
                url,
                headers=merged_headers,
                params=merged_params,
                data=data,
                json=json,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="The external service timed out. Please try again later.",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail="The external service is unavailable. Please try again later.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail="The external service returned an unexpected response.",
            ) from exc

    async def close(self) -> None:
        await self.client.aclose()
