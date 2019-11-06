"""
This app serves as a proxy handling sticky sessions for socketio.
"""

from datetime import timedelta
from functools import wraps
from random import choice
import logging

from aiocache import Cache
from aiocache.serializers import JsonSerializer
from sanic import Sanic
from sanic.response import redirect, text
from sanic.exceptions import SanicException
from sanic_cors import CORS
from sanic_jwt_extended import JWTManager
from sanic_jwt_extended.decorators import (
    get_jwt_data,
    get_jwt_data_in_request_header,
    verify_jwt_data_type,
)

from ora_backend.config import SOCKETIO_RUN_CONFIG, CORS_ORIGINS, JWT_SECRET_KEY
from ora_backend.utils.crypto import unsign_str


app = Sanic(__name__)

app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
app.config["JWT_TOKEN_LOCATION"] = "cookies"
app.config["JWT_ERROR_MESSAGE_KEY"] = "error"
app.config["CORS_AUTOMATIC_OPTIONS"] = True
app.config["CORS_SUPPORTS_CREDENTIALS"] = True

# Middlewares
cache = Cache(serializer=JsonSerializer())
JWTManager(app)
# CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

logging.getLogger("sanic_cors").level = logging.DEBUG

# Register error handlers
from ora_backend.exceptions import sanic_error_handler

app.error_handler.add(SanicException, sanic_error_handler)

SOCKETIO_APP_URLS = [
    "http://192.168.1.141:8081/socket.io",
    "http://192.168.1.141:8082/socket.io",
    "http://192.168.1.141:8083/socket.io",
]

ALLOWED_ORIGINS = set(CORS_ORIGINS)


async def validate_token(token, token_type="access"):
    token = unsign_str(token.strip())

    jwt_token_data = await get_jwt_data(app, token)
    await verify_jwt_data_type(jwt_token_data, token_type)
    return jwt_token_data


def cors():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            response = await f(request, *args, **kwargs)
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers[
                "Access-Control-Allow-Headers"
            ] = "Content-Type, authorization"
            # print('yay')
            # print(request.cookies.get('access_token'))
            # if request.cookies:
            # response.headers["Authorization"] = request.cookies.get('access_token', '')
            # response.headers['Access-Control-Allow-Origin'] = '*'
            if "ORIGIN" in request.headers:
                origin = request.headers["ORIGIN"]
                if origin in ALLOWED_ORIGINS:
                    response.headers["Access-Control-Allow-Origin"] = origin

            return response

        return decorated_function

    return decorator


@app.route(
    "/socket.io", methods=["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
)
@cors()
async def routing(request):
    # if request.method == "OPTIONS":
    #     return text('true')
    token = request.headers.get("Authorization")
    if token:
        print("yay")
        print(request.url)
        token = token.replace("Bearer ", "")
        user_id = (await validate_token(token))["identity"]["id"]
        print("passed")
        session = await cache.get("lb_session_{}".format(user_id))

        # If not registered
        if not session:
            instance_url = choice(SOCKETIO_APP_URLS)
            await cache.set(
                "lb_session_{}".format(user_id),
                {"user": user_id, "instance_url": instance_url},
            )
            return redirect("{}/?{}".format(instance_url, request.query_string))

        return redirect("{}/?{}".format(session["instance_url"], request.query_string))

    return redirect("{}/?{}".format(choice(SOCKETIO_APP_URLS), request.query_string))


if __name__ == "__main__":
    app.run(**SOCKETIO_RUN_CONFIG)
