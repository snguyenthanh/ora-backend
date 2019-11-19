from uuid import uuid4
from sanic.response import json
from sanic_jwt_extended import create_access_token, create_refresh_token

from ora_backend.models import User, Visitor, Setting
from ora_backend.views.urls import root_blueprint as blueprint
from ora_backend.utils.auth import get_token_data_from_request
from ora_backend.utils.crypto import sign_str
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import validate_request


@blueprint.route("/")
async def root(request):
    return json({"hello": "world"})


async def login(request, identity):
    # Identity can be any data that is json serializable
    access_token = await create_access_token(identity=identity, app=request.app)
    refresh_token = await create_refresh_token(identity=identity, app=request.app)

    # Sign the tokens to avoid modifications
    signed_access_token = sign_str(access_token)
    signed_refresh_token = sign_str(refresh_token)

    # Attach the tokens in a cookie
    response = json({"user": identity, "access_token": signed_access_token})
    response.cookies["access_token"] = signed_access_token
    response.cookies["refresh_token"] = signed_refresh_token
    response.cookies["access_token"]["httponly"] = True
    response.cookies["refresh_token"]["httponly"] = True

    return response


@blueprint.route("/anonymous/login", methods=["POST"])
@unpack_request
@validate_request(schema="anonymous_login", skip_args=True)
async def anonymous_login(request, *, req_body, **kwargs):
    user = await Visitor.login(**req_body, is_anonymous=True)
    return await login(request, user)


@blueprint.route("/visitor/login", methods=["POST"])
@unpack_request
@validate_request(schema="user_login", skip_args=True)
async def visitor_login(request, *, req_body, **kwargs):
    user = await Visitor.login(**req_body)
    return await login(request, user)


@blueprint.route("/login", methods=["POST"])
@unpack_request
@validate_request(schema="user_login", skip_args=True)
async def user_login(request, *, req_body, **kwargs):
    """
    Return an access token and refresh token to user,
    if the login credentials of email and password are correct.

    Note:
        Invalid token received in any protected routes
        will return a 422 response.

    Return HTTP Codes:
        400: Missing `email` and/or `password` in request's body.
        401: Invalid email or password.
    """
    user = await User.login(**req_body)
    return await login(request, user)


@blueprint.route("/refresh", methods=["POST"])
async def create_new_access_token(request):
    jwt_token_data = await get_token_data_from_request(request, token_type="refresh")
    access_token = await create_access_token(
        identity=jwt_token_data["identity"], app=request.app
    )
    signed_access_token = sign_str(access_token)
    response = json({"access_token": signed_access_token})
    response.cookies["access_token"] = signed_access_token
    response.cookies["refresh_token"] = request.cookies["refresh_token"]
    response.cookies["access_token"]["httponly"] = True
    response.cookies["refresh_token"]["httponly"] = True

    return response


@blueprint.route("/settings", methods=["GET"])
async def get_settings(request):
    settings = await Setting.get(many=True, limit=99)
    # Todo: Patch settings
    return {"data": settings}
