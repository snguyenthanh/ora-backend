from sanic_jwt_extended.decorators import (
    get_jwt_data,
    get_jwt_data_in_request_header,
    verify_jwt_data_type,
)
from sanic_jwt_extended.exceptions import NoAuthorizationError

from ora_backend import app
from ora_backend.utils.crypto import unsign_str


async def validate_token(token, token_type="access"):
    token = unsign_str(token)
    jwt_token_data = await get_jwt_data(app, token)
    # jwt_token_data = await get_jwt_data_in_request_header(app, request)

    await verify_jwt_data_type(jwt_token_data, token_type)
    return jwt_token_data


async def get_token_from_request(request, token_type="access"):
    if not request.cookies:
        raise NoAuthorizationError()

    token = None
    if (token_type == "access" and "access_token" not in request.cookies) or (
        token_type == "refresh" and "refresh_token" not in request.cookies
    ):
        raise NoAuthorizationError()

    token: str = (
        request.cookies["access_token"]
        if token_type == "access"
        else request.cookies["refresh_token"]
    )
    return token


async def get_token_data_from_request(request, token_type="access"):
    token = await get_token_from_request(request, token_type=token_type)
    return await validate_token(token, token_type=token_type)


async def get_token_requester(token: str, token_type="access"):
    jwt_token_data = await validate_token(token, token_type=token_type)
    return jwt_token_data["identity"]


async def get_token_requester_from_request(request):
    jwt_token_data = await get_token_data_from_request(request)
    return jwt_token_data["identity"]
