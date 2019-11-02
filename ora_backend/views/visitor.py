from sanic.response import json
from sanic.exceptions import Forbidden, NotFound, InvalidUsage

from ora_backend.constants import ROLES
from ora_backend.views.urls import visitor_blueprint as blueprint
from ora_backend.models import Visitor, Chat, ChatMessage, User, ChatMessageSeen
from ora_backend.schemas import to_boolean
from ora_backend.utils.links import generate_pagination_links, generate_next_page_link
from ora_backend.utils.query import get_visitors_with_most_recent_chats
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import (
    validate_request,
    validate_permission,
    validate_against_schema,
)


@validate_permission
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


@blueprint.route("/<visitor_id>/messages", methods=["GET"])
@unpack_request
@validate_permission
async def get_chat_messages_of_visitor(
    request, visitor_id, *, requester, req_args=None, query_params=None, **kwargs
):
    visitor_id = visitor_id.strip()
    req_args = req_args or {}
    query_params = query_params or {}
    starts_from_unread = to_boolean(req_args.pop("starts_from_unread", False))

    # Take the before_id, after_id and starts_from_unread
    allowed_args = {"before_id", "after_id"}
    for key in set(list(req_args.keys()) + list(query_params.keys())):
        if key in allowed_args:
            kwargs[key] = req_args.pop(key, None) or query_params.pop(key, None)

    before_id = kwargs.pop("before_id", None)
    after_id = kwargs.pop("after_id", None)
    if before_id and starts_from_unread:
        raise InvalidUsage(
            "Both fields 'before_id' and 'starts_from_unread' cannot present in the same request"
        )
    if after_id and starts_from_unread:
        raise InvalidUsage(
            "Both fields 'after_id' and 'starts_from_unread' cannot present in the same request"
        )
    if after_id and before_id:
        raise InvalidUsage(
            "Both fields 'before_id' and 'after_id' cannot present in the same request"
        )

    # Ensure that the chat exists
    try:
        chat = await Chat.get(visitor_id=visitor_id)
    except NotFound:
        messages = []
    else:
        last_read_msg_id = None
        if starts_from_unread:
            last_read_message = await ChatMessageSeen.get_or_create(
                staff_id=requester["id"], chat_id=chat["id"]
            )
            last_read_msg_id = last_read_message["last_seen_msg_id"]
        before_id = before_id or last_read_msg_id
        messages = await ChatMessage.get(
            chat_id=chat["id"],
            **req_args,
            **query_params,
            before_id=before_id,
            after_id=after_id,
            exclude=not starts_from_unread,
        )

    prev_link = generate_pagination_links(
        request.url,
        messages,
        field="before_id",
        index=0,
        exclude={"after_id", "starts_from_unread"},
    ).get("next")
    next_link = generate_pagination_links(
        request.url,
        messages,
        field="after_id",
        index=-1,
        exclude={"before_id", "starts_from_unread"},
    ).get("next")

    links = {}
    if prev_link:
        links["prev"] = prev_link
    if next_link:
        links["next"] = next_link
    return json({"data": messages, "links": links})


@blueprint.route("/most_recent", methods=["GET"])
@unpack_request
@validate_permission
async def most_recent_visitors(
    request, *, req_args=None, requester=None, query_params=None, **kwargs
):
    # A visitor or agent cannot get other visitors
    if "name" in requester or requester["role_id"] >= ROLES.inverse["agent"]:
        raise Forbidden("You are not allowed to perform this action.")

    req_args = req_args or {}
    query_params = query_params or {}
    params = validate_against_schema(
        {**req_args, **query_params}, "query_params_get_visitors"
    )
    visitors = await get_visitors_with_most_recent_chats(
        Chat, ChatMessage, Visitor, User, requester, **params
    )

    next_page_link = generate_next_page_link(
        request.url, cur_page=params.get("page", 0)
    )
    return json({"data": visitors, "links": {"next": next_page_link or {}}})
