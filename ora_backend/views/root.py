from uuid import uuid4
from sanic.response import json
from sanic_jwt_extended import create_access_token, create_refresh_token

from ora_backend.models import User
from ora_backend.views.urls import root_blueprint as blueprint
from ora_backend.utils.authentication import validate_token
from ora_backend.utils.crypto import sign_value
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import validate_request


@blueprint.route("/")
async def root(request):
    return json({"hello": "world"})


@blueprint.route("/login", methods=["POST"])
@unpack_request
@validate_request(schema="user_login", skip_args=True)
async def login(request, *, req_args, req_body, **kwargs):
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

    # Identity can be any data that is json serializable
    access_token = await create_access_token(identity=user, app=request.app)
    refresh_token = await create_refresh_token(identity=user, app=request.app)

    # Sign the tokens to avoid modifications
    signed_access_token = sign_value(access_token)
    signed_refresh_token = sign_value(refresh_token)

    # Attach the tokens in a cookie
    response = json({"user": user})
    response.cookies["access_token"] = signed_access_token
    response.cookies["refresh_token"] = signed_refresh_token

    # return json({"user": user, "access_token": access_token, "refresh_token": refresh_token})
    return response


@blueprint.route("/refresh", methods=["POST"])
async def create_new_access_token(request):
    jwt_token_data = await validate_token(request, token_type="refresh")
    access_token = await create_access_token(
        identity=jwt_token_data["identity"], app=request.app
    )
    # return json({"access_token": access_token})
    signed_access_token = sign_value(access_token)
    response = json()
    response.cookies["access_token"] = signed_access_token
    response.cookies["refresh_token"] = request.cookies["refresh_token"]
    return response
