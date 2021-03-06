from sanic.response import json
from sanic.exceptions import Forbidden, NotFound, InvalidUsage

from ora_backend.constants import ROLES
from ora_backend.views.urls import visitor_blueprint as blueprint
from ora_backend.models import (
    Visitor,
    Chat,
    ChatMessage,
    User,
    ChatMessageSeen,
    BookmarkVisitor,
    ChatUnhandled,
    ChatFlagged,
    StaffSubscriptionChat,
)
from ora_backend.schemas import to_boolean
from ora_backend.utils.links import generate_pagination_links, generate_next_page_link
from ora_backend.utils.query import (
    get_visitors_with_most_recent_chats,
    get_bookmarked_visitors,
    get_top_unread_visitors,
    get_subscribed_staffs_for_visitor,
    get_non_normal_visitors,
    get_staff_unhandled_visitors,
    get_self_subscribed_visitors,
    get_handled_chats,
)
from ora_backend.utils.request import unpack_request
from ora_backend.utils.validation import (
    validate_request,
    validate_permission,
    validate_against_schema,
)
from ora_backend.worker.tasks import send_email_to_new_visitor


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


@validate_request(schema="visitor_write", skip_args=True)
async def visitor_create(req, *, req_args, req_body, **kwargs):
    visitor = await Visitor.add(**req_body)

    # Send email
    send_email_to_new_visitor.apply_async(
        ([visitor["email"]], visitor),
        expires=60 * 5,  # seconds
        retry_policy={"interval_start": 10},
    )

    return {"data": visitor}


@blueprint.route("/bookmarked", methods=["GET"])
@unpack_request
@validate_permission
async def visitor_get_many_bookmarked(
    request,
    *,
    req_args=None,
    req_body=None,
    query_params=None,
    requester=None,
    **kwargs,
):
    visitors = await get_bookmarked_visitors(
        Visitor, BookmarkVisitor, requester["id"], **query_params
    )
    return json(
        {"data": visitors, "links": generate_pagination_links(request.url, visitors)}
    )


@blueprint.route("/unread", methods=["GET"])
@unpack_request
@validate_permission
async def get_unread_visitors(request, *, req_args, req_body, requester, **kwargs):
    staff_id = requester["id"]
    visitors = await get_top_unread_visitors(Visitor, Chat, staff_id)
    return json({"data": visitors})


@validate_permission
async def visitor_get_many(request, *, req_args, query_params, **kwargs):
    query_params = query_params or {}
    exclude_unhandled = req_args.pop("exclude_unhandled", "false")
    exclude_unhandled = exclude_unhandled.lower() in {"1", "true"}

    if exclude_unhandled:
        visitors = await get_handled_chats(Visitor, **query_params)
    else:
        visitors = await Visitor.get(
            many=True, decrease=True, **req_args, **query_params
        )
    return {"data": visitors, "links": generate_pagination_links(request.url, visitors)}


@blueprint.route("/", methods=["GET", "POST"])
@unpack_request
async def visitor_route_multiple(request, *, req_args, req_body, **kwargs):
    call_funcs = {
        "GET": visitor_get_many,
        "POST": visitor_create,
        # "DELETE": user_delete,
    }

    response = await call_funcs[request.method](
        request, req_args=req_args, req_body=req_body, **kwargs
    )
    return json(response)


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


@blueprint.route("/<visitor_id>/subscribed_staffs", methods=["GET"])
@unpack_request
@validate_permission
async def get_subscribed_staffs_for_visitor_route(
    request, visitor_id, *, requester=None, req_args=None, query_params=None, **kwargs
):
    visitor_id = visitor_id.strip()
    subscribed_staffs = await get_subscribed_staffs_for_visitor(visitor_id)

    return json(
        {
            "data": subscribed_staffs,
            "links": generate_pagination_links(request.url, subscribed_staffs),
        }
    )


@blueprint.route("/subscribed", methods=["GET"])
@unpack_request
@validate_permission
async def get_subscribed_visitors_for_staff_route(
    request, *, req_args=None, query_params=None, requester=None, **kwargs
):
    req_args = req_args or {}
    exclude_unhandled = req_args.get("exclude_unhandled", "false")
    exclude_unhandled = exclude_unhandled.lower() in {"1", "true"}

    # Return the staff's unhandled visitors
    staff_id = requester["id"]
    subscribed_visitors = await get_self_subscribed_visitors(
        Visitor,
        Chat,
        StaffSubscriptionChat,
        staff_id,
        **query_params,
        exclude_unhandled=exclude_unhandled,
    )

    return json(
        {
            "data": subscribed_visitors,
            "links": generate_pagination_links(request.url, subscribed_visitors),
        }
    )


@blueprint.route("/unhandled", methods=["GET"])
@unpack_request
@validate_permission
async def get_unhandled_staffs_for_visitor_route(
    request, *, req_args=None, query_params=None, requester=None, **kwargs
):
    req_args = req_args or {}
    query_params = query_params or {}
    if "all" in req_args and req_args["all"].lower() in {"true", "1"}:
        # unhandled_visitors = await get_non_normal_visitors(
        #     ChatUnhandled, **query_params
        # )
        unhandled_visitors = await get_staff_unhandled_visitors(
            StaffSubscriptionChat, None, **query_params
        )
    else:
        # Return the staff's unhandled visitors
        staff_id = requester["id"]
        unhandled_visitors = await get_staff_unhandled_visitors(
            StaffSubscriptionChat, staff_id, **query_params
        )

    return json(
        {
            "data": unhandled_visitors,
            "links": generate_pagination_links(request.url, unhandled_visitors),
        }
    )


@blueprint.route("/flagged", methods=["GET"])
@unpack_request
@validate_permission
async def get_subscribed_staffs_for_visitor_route(
    request, *, query_params=None, **kwargs
):
    query_params = query_params or {}
    flagged_visitors = await get_non_normal_visitors(
        ChatFlagged,
        **query_params,
        extra_fields=[
            "chat_flagged.flag_message AS flag_message",
            "chat_flagged.created_at AS flagged_timestamp",
        ],
    )
    return json(
        {
            "data": flagged_visitors,
            "links": generate_pagination_links(request.url, flagged_visitors),
        }
    )


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
        exclude = after_id is not None or before_id is not None
        if starts_from_unread:
            last_read_message = await ChatMessageSeen.get_or_create(
                staff_id=requester["id"], chat_id=chat["id"]
            )
            last_read_msg_id = last_read_message["last_seen_msg_id"]

            # If the chat hasnt been read at all, starts from top
            if not last_read_msg_id:
                first_msg = await ChatMessage.get_first_message_of_chat(chat["id"])
                # If there is no chat messages at all, return []
                if not first_msg:
                    return json({"data": [], "links": {}})

                before_id = None
                after_id = first_msg["id"]
                exclude = False
            else:
                before_id = last_read_msg_id
                exclude = False

        # after_id = after_id or last_read_msg_id
        messages = await ChatMessage.get(
            chat_id=chat["id"],
            **req_args,
            **query_params,
            before_id=before_id,
            after_id=after_id,
            exclude=exclude,
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


@validate_request(schema="bookmark_visitor_read")
async def get_visitor_bookmark(
    request, visitor_id, *, req_args, req_body, requester, **kwargs
):
    staff_bookmark = await BookmarkVisitor.get_or_create(
        staff_id=requester["id"], visitor_id=visitor_id
    )
    return {"data": staff_bookmark}


@validate_request(schema="bookmark_visitor_write", update=True)
async def update_visitor_bookmark(
    request, visitor_id, *, req_args=None, req_body=None, requester=None, **kwargs
):
    staff_bookmark = await BookmarkVisitor.update_or_create(
        {"staff_id": requester["id"], "visitor_id": visitor_id}, req_body
    )
    return {"data": staff_bookmark}


@blueprint.route("/<visitor_id>/bookmark", methods=["GET", "PUT", "PATCH"])
@unpack_request
@validate_permission
async def visitor_bookmark_route(
    request, visitor_id, *, req_args=None, req_body=None, requester=None, **kwargs
):
    visitor_id = visitor_id.strip()

    call_funcs = {
        "GET": get_visitor_bookmark,
        "PUT": update_visitor_bookmark,
        "PATCH": update_visitor_bookmark,
    }

    response = await call_funcs[request.method](
        request,
        visitor_id,
        req_args=req_args,
        req_body=req_body,
        requester=requester,
        **kwargs,
    )
    return json(response)


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


@blueprint.route("/<visitor_id>/last_seen", methods=["GET", "PUT", "PATCH"])
@unpack_request
@validate_permission
async def message_last_seen_route(
    request, visitor_id, *, req_args, req_body, requester, **kwargs
):
    visitor_id = visitor_id.strip()
    chat_info = await Chat.get(visitor_id=visitor_id)

    call_funcs = {
        "GET": get_last_seen_message_for_staff,
        "PUT": update_last_seen_message_by_staff,
        "PATCH": update_last_seen_message_by_staff,
    }
    response = await call_funcs[request.method](
        request,
        chat_info["id"],
        req_args=req_args,
        req_body=req_body,
        requester=requester,
    )
    return json(response)
