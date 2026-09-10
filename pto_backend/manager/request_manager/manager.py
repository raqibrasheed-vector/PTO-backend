from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from pto_backend.settings import settings


class AsyncAPIClient:
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
    ):
        self.base_url = url
        self.default_headers = headers or {}
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return await self._request("GET", endpoint, params=params, headers=headers)

    async def post(
        self,
        endpoint: str,
        data: Any = None,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
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
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
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
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self._request("DELETE", endpoint, headers=headers)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Dict[str, Any] = {},
        json: Dict[str, Any] = {},
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
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
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=str(e.args))
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=str(e.args))

    async def close(self) -> None:
        await self.client.aclose()