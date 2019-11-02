from sanic.response import json

from ora_backend.views.urls import chat_blueprint as blueprint
from ora_backend.models import ChatMessageSeen
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import validate_request, validate_permission


@validate_request(schema="chat_message_seen_write", update=True)
async def update_last_seen_message_by_staff(
    request, chat_id, *, req_args, req_body, requester, **kwargs
):
    last_seen_message = await ChatMessageSeen.update_or_create(
        {"staff_id": requester["id"], "chat_id": chat_id}, req_body
    )
    return {"data": last_seen_message}


async def get_last_seen_message_for_staff(
    request, chat_id, *, req_args, req_body, requester
):
    last_seen_message = await ChatMessageSeen.get_or_create(
        staff_id=requester["id"], chat_id=chat_id
    )
    return {"data": last_seen_message}


@blueprint.route("/<chat_id>/last_seen", methods=["GET", "PUT", "PATCH"])
@unpack_request
@validate_permission
async def message_last_seen_route(
    request, chat_id, *, req_args, req_body, requester, **kwargs
):
    chat_id = chat_id.strip()

    call_funcs = {
        "GET": get_last_seen_message_for_staff,
        "PUT": update_last_seen_message_by_staff,
        "PATCH": update_last_seen_message_by_staff,
    }
    response = await call_funcs[request.method](
        request, chat_id, req_args=req_args, req_body=req_body, requester=requester
    )
    return json(response)
