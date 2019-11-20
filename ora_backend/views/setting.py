from sanic.exceptions import Forbidden
from sanic.response import json

from ora_backend.constants import ROLES
from ora_backend.models import Setting
from ora_backend.views.urls import setting_blueprint as blueprint
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import validate_request, validate_permission


async def get_all_settings(request, **kwargs):
    settings = await Setting.get(many=True, limit=100)
    settings_as_dict = {setting["key"]: setting["value"] for setting in settings}
    return {"data": settings_as_dict}


@validate_permission
async def change_global_settings(
    request, *, req_args=None, req_body=None, requester, **kwargs
):
    if requester["role_id"] != ROLES.inverse["admin"]:
        return Forbidden("Only admins are allowed to change settings")

    for key, value in req_body:
        await Setting.modify_if_exists({"key": key}, {"value": value})
    return {
        "data": None
    }


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
