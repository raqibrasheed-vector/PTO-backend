from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ModelsPagination(BaseModel):
    total_pages: int
    total_records: int
    page: int
    start: int
    end: int


class PaginationResponse(ModelsPagination, Generic[T]):
    data: T