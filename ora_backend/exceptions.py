"""
A collection of custom exceptions to return to client.
"""
from sanic.response import json
from sanic.exceptions import SanicException

# from ora_backend.config import CORS_ORIGINS


def sanic_error_handler(request, exception):
    status_code = 500
    exc_message = exception

    if hasattr(exception, "args") and exception.args:
        exc_message = exception.args[0]
    if hasattr(exception, "status_code"):
        status_code = exception.status_code

    if isinstance(exc_message, str):
        exc_message = {"msg": [exc_message]}

    if "ORIGIN" in request.headers:
        access_control_allow_origin = request.headers["ORIGIN"]
    else:
        access_control_allow_origin = "https://chatwithora.com"

    return json(
        {"error": exc_message},
        status=status_code,
        headers={
            "Access-Control-Allow-Origin": access_control_allow_origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )


class SchemaValidationError(SanicException):
    def __init__(self, message, status_code=400):
        super().__init__(message, status_code)


class LoginFailureError(SanicException):
    def __init__(self, message=None, status_code=401):
        if not message:
            message = "The email or password was incorrect."
        super().__init__(message, status_code)


class UniqueViolationError(SanicException):
    """
    An overwritten error for asyncpg.exceptions.UniqueViolationError.

    Note:
        asyncpg.exceptions.UniqueViolationError:
            duplicate key value violates unique constraint "urls_pkey"
        DETAIL:  Key (id)=(1) already exists.
    """

    def __init__(self, error=None, status_code=400):
        if error and isinstance(error, dict):
            message = "The {} with {}.".format(error["table_name"], error["detail"])
        else:
            message = "The resource has already existed"
        super().__init__(message, status_code)


def unique_violation_error_handler(request, exception):
    raise UniqueViolationError()
