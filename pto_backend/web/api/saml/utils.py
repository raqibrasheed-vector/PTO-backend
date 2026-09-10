from fastapi import Request

from pto_backend.manager.saml.manager import SAMLManager


def saml_function_wrapper(request: Request) -> SAMLManager:

    return SAMLManager(request=request)
