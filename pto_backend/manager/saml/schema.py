from pydantic import BaseModel
from typing import Dict


class SAMLResponse(BaseModel):
    https: str
    http_host: str
    server_port: str
    script_name: str
    get_data: Dict[str, str]
    post_data: Dict[str,str]
    query_string: str