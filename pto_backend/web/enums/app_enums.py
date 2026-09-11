import enum

from pto_backend.settings import settings


class AppCookieEnums(str, enum.Enum):
    AccessToken = settings.access_token_cookie_name
    SessionToken = settings.session_token_cookie_name
