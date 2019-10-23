from sanic.response import json
from sanic.exceptions import Forbidden

from ora_backend.views.urls import visitor_blueprint as blueprint
from ora_backend.models import Visitor
from ora_backend.utils.exceptions import raise_role_authorization_exception
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import validate_request, validate_permission


@validate_request(schema="visitor_read", skip_body=True)
async def visitor_retrieve(req, *, req_args, req_body, **kwargs):
    return {"data": await Visitor.get(**req_args)}


# @validate_request(schema="user_write")
# @validate_permission(model=User)
# async def user_replace(req, *, req_args, req_body, **kwargs):
#     return {"data": await User.modify(req_args, req_body)}


@validate_permission
@validate_request(schema="visitor_write", update=True)
async def visitor_update(req, *, req_args, req_body, requester, **kwargs):
    visitor_id = req_args["id"]

    # Only the visitor himself can modify
    if requester["id"] != visitor_id:
        raise Forbidden("Only the visitor himself can modify.")

    return {"data": await Visitor.modify(req_args, req_body)}


@blueprint.route("/", methods=["POST"])
@unpack_request
@validate_request(schema="visitor_write", skip_args=True)
async def visitor_create(req, *, req_args, req_body, **kwargs):
    return json({"data": await Visitor.add(**req_body)})


@blueprint.route("/<visitor_id>", methods=["GET", "PUT", "PATCH"])
@unpack_request
async def visitor_route_single(
    request, visitor_id, *, req_args=None, req_body=None, **kwargs
):
    visitor_id = visitor_id.strip()

    call_funcs = {
        "GET": visitor_retrieve,
        "PUT": visitor_update,
        "PATCH": visitor_update,
        # "DELETE": user_delete,
    }

    response = await call_funcs[request.method](
        request, req_args={**req_args, "id": visitor_id}, req_body=req_body, **kwargs
    )
    return json(response)
