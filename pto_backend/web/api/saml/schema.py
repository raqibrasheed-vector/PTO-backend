from pydantic import BaseModel


class SignInResponse(BaseModel):
    url: str


class Token(BaseModel):
    access_token: str
    token_type: str
