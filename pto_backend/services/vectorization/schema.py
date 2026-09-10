from pydantic import BaseModel


class DocumentChunk(BaseModel):
    """A single semantically-retrieved chunk of a source document."""

    text: str


class VectorSearchResult(BaseModel):
    """Result of building a vectorstore from an upload and searching it."""

    employee_id: str
    file_name: str
    query: str
    results: list[DocumentChunk]
