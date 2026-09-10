from datetime import datetime

from pydantic import BaseModel


class TokenSchema(BaseModel):
    email: str
    group: str
    iat: datetime
    exp: datetime
    iss: str | None = "actalent"
    aud: str
    session_id: str
    name: str
