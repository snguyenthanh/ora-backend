from sanic.exceptions import Forbidden
from sanic.response import json

from ora_backend import cache
from ora_backend.constants import ROLES, CACHE_SETTINGS
from ora_backend.models import Setting
from ora_backend.views.urls import setting_blueprint as blueprint
from ora_backend.utils.request import unpack_request
from ora_backend.utils.settings import get_latest_settings
from ora_backend.utils.validation import validate_request, validate_permission


async def get_all_settings(request, **kwargs):
    return {"data": await get_latest_settings()}


@validate_permission
async def change_global_settings(
    request, *, req_args=None, req_body=None, requester, **kwargs
):
    if requester["role_id"] != ROLES.inverse["admin"]:
        return Forbidden("Only admins are allowed to change settings")

    for key, value in req_body.items():
        await Setting.modify_if_exists({"key": key}, {"value": value})

    # Update the settings in cache
    settings = await get_latest_settings()
    await cache.set(CACHE_SETTINGS, settings, namespace="settings")

    return {"data": None}


@blueprint.route("/", methods=["GET", "PUT", "PATCH"])
@unpack_request
async def get_settings(request, *, req_args=None, req_body=None, **kwargs):
    call_funcs = {
        "GET": get_all_settings,
        "PUT": change_global_settings,
        "PATCH": change_global_settings,
        # "DELETE": user_delete,
    }

    response = await call_funcs[request.method](
        request, req_args=req_args, req_body=req_body
    )
    return json(response)
