from sanic.response import json
from sanic.exceptions import Forbidden

from ora_backend.constants import ROLES
from ora_backend.views.urls import user_blueprint as blueprint
from ora_backend.models import (
    User,
    NotificationStaff,
    NotificationStaffRead,
    StaffSubscriptionChat,
)
from ora_backend.utils.assign import (
    reset_all_volunteers_in_cache,
    auto_assign_staff_to_chat,
)
from ora_backend.utils.exceptions import (
    raise_role_authorization_exception,
    raise_permission_exception,
)
from ora_backend.utils.links import generate_pagination_links
from ora_backend.utils.query import (
    get_number_of_unread_notifications_for_staff,
    get_visitors_with_no_assigned_staffs,
    get_one_latest,
    delete_many,
)
from ora_backend.utils.request import unpack_request
from ora_backend.utils.settings import get_latest_settings
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

    new_user = await User.modify(req_args, req_body)

    # When a staff is disabled:
    # - Remove him from all subscriptions
    # - If he is the only staff in a chat => re-assign
    if req_body.get("disabled", False):
        is_disabled = req_body.get("disabled", False)
        if is_disabled:
            # Remove all subscriptions
            await delete_many(StaffSubscriptionChat, staff_id=user_id)

        # Update the list of volunteers to assign
        await reset_all_volunteers_in_cache()

        settings = await get_latest_settings()
        if settings.get("auto_reassign", 0):
            # Re-assign a new staff
            # to the visitors with no assigned staffs
            visitors = await get_visitors_with_no_assigned_staffs()
            for visitor in visitors:
                await auto_assign_staff_to_chat(visitor["id"])

    return {"data": new_user}


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


@validate_request(schema="notification_staff_read", skip_body=True)
async def noti_staff_retrieve(request, *, req_args=None, query_params=None, **kwargs):
    notifs = await NotificationStaff.get(
        **req_args, **query_params, many=True, decrease=True
    )
    staff_id = req_args["staff_id"]
    number_of_unread_notis = await get_number_of_unread_notifications_for_staff(
        staff_id, NotificationStaffRead, NotificationStaff
    )
    return {
        "data": notifs,
        "num_of_unread": number_of_unread_notis,
        "links": generate_pagination_links(request.url, notifs),
    }


async def noti_staff_refresh(request, *, req_args=None, query_params=None, **kwargs):
    staff_id = req_args["staff_id"]
    latest_read_noti = await get_one_latest(NotificationStaff, staff_id=staff_id)
    await NotificationStaffRead.update_or_create(
        {"staff_id": staff_id},
        {
            "last_read_internal_id": latest_read_noti.internal_id
            if latest_read_noti
            else None
        },
    )
    return {"data": None}


@blueprint.route("/notifications", methods=["GET", "PUT"])
@unpack_request
@validate_permission
async def notification_staff_route(
    request,
    *,
    req_args=None,
    req_body=None,
    query_params=None,
    requester=None,
    **kwargs
):
    if "role_id" not in requester:
        raise Forbidden("Only staffs can receive notifications")
    staff_id = requester["id"]

    call_funcs = {
        "GET": noti_staff_retrieve,
        # "POST": noti_staff_create,
        "PUT": noti_staff_refresh,
        # "PATCH": visitor_update,
        # "DELETE": user_delete,
    }

    response = await call_funcs[request.method](
        request,
        req_args={"staff_id": staff_id},
        req_body=req_body,
        query_params=query_params,
        **kwargs
    )
    return json(response)
