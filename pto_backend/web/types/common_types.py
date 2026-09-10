from pydantic import BaseModel


class CurrentUser(BaseModel):
    name: str
    email: str
    group: str
    session_id: str