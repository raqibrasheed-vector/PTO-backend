from pydantic import BaseModel


class SAMLResponse(BaseModel):
    https: str
    http_host: str
    server_port: str
    script_name: str
    get_data: dict[str, str]
    post_data: dict[str, str]
    query_string: str
