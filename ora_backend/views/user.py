from sanic.response import json

from ora_backend.constants import ROLES
from ora_backend.views.urls import user_blueprint as blueprint
from ora_backend.models import User
from ora_backend.utils.exceptions import (
    raise_role_authorization_exception,
    raise_permission_exception,
)
from ora_backend.utils.links import generate_pagination_links
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import validate_request, validate_permission


@validate_request(schema="user_read", skip_body=True)
async def user_retrieve(
    req, *, req_args, req_body, requester=None, many=True, query_params, **kwargs
):
    # The requester can only get the users from his org
    if "organisation_id" not in requester:
        raise_permission_exception()
    req_args["organisation_id"] = requester["organisation_id"]

    data = await User.get(**req_args, many=many, **query_params)
    if many:
        return {"data": data, "links": generate_pagination_links(req.url, data)}
    return {"data": data}


@validate_request(schema="user_write", skip_args=True)
async def user_create(req, *, req_args, req_body, requester, **kwargs):
    create_user_role_id = req_body.get("role_id", 3)

    # An user cannot create an account with equal/larger position than itself
    if (
        create_user_role_id < requester["role_id"]
        or requester["role_id"] >= ROLES.inverse["agent"]
    ):
        raise_role_authorization_exception(create_user_role_id)

    # Inject the organisation_id to the new user
    # An user can only create a new user within its org
    req_body["organisation_id"] = requester["organisation_id"]

    return {"data": await User.add(**req_body)}


# @validate_request(schema="user_write")
# @validate_permission(model=User)
# async def user_replace(req, *, req_args, req_body, **kwargs):
#     return {"data": await User.modify(req_args, req_body)}


@validate_request(schema="user_write", update=True)
async def user_update(req, *, req_args, req_body, requester, **kwargs):
    user_id = req_args["id"]
    update_user = await User.get(id=user_id)

    # Only the user himself or the higher-level acc can modify a lower one
    if requester["id"] != user_id and (
        update_user["role_id"] < requester["role_id"]
        or requester["role_id"] >= ROLES.inverse["agent"]
    ):
        raise_role_authorization_exception(update_user["role_id"], action="update")

    return {"data": await User.modify(req_args, req_body)}


@validate_request(schema="user_read", skip_body=True)
async def user_delete(req, *, req_args, req_body, requester, **kwargs):
    user_id = req_args["id"]
    delete_user = await User.get(id=user_id)

    # Only the user himself or the higher-level acc can modify a lower one
    if (
        requester["id"] != user_id and delete_user["role_id"] < requester["role_id"]
    ) or requester["role_id"] >= ROLES.inverse["agent"]:
        raise_role_authorization_exception(delete_user["role_id"], action="delete")

    await User.remove(**req_args)


@blueprint.route("/", methods=["GET", "POST"])
@unpack_request
@validate_permission
async def user_route(
    request, *, req_args=None, req_body=None, query_params=None, requester=None
):
    """Only supervisor and admin could see and create users."""
    call_funcs = {"GET": user_retrieve, "POST": user_create}
    response = await call_funcs[request.method](
        request,
        req_args=req_args,
        req_body=req_body,
        query_params=query_params,
        requester=requester,
    )
    return json(response)


@blueprint.route("/<user_id>", methods=["GET", "PUT", "PATCH"])
@unpack_request
@validate_permission
async def user_route_single(
    request, user_id, *, req_args=None, req_body=None, requester, query_params
):
    user_id = user_id.strip()

    call_funcs = {
        "GET": user_retrieve,
        "PUT": user_update,
        "PATCH": user_update,
        # "DELETE": user_delete,
    }

    response = await call_funcs[request.method](
        request,
        req_args={**req_args, "id": user_id},
        req_body=req_body,
        many=False,
        query_params=query_params,
        requester=requester,
    )
    return json(response)
