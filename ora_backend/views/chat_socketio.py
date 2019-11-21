from os import environ as _environ
from pprint import pprint

import socketio
from socketio.exceptions import ConnectionRefusedError
from sanic.exceptions import Unauthorized, NotFound
from sanic_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import ExpiredSignatureError
import time

from ora_backend import app, cache
from ora_backend.constants import (
    UNCLAIMED_CHATS_PREFIX,
    ONLINE_USERS_PREFIX,
    ROLES,
    MONITOR_ROOM_PREFIX,
    ONLINE_VISITORS_PREFIX,
    CACHE_SETTINGS,
)
from ora_backend.models import (
    Chat,
    ChatMessage,
    Organisation,
    Visitor,
    User,
    ChatUnclaimed,
    StaffSubscriptionChat,
    ChatUnhandled,
    ChatFlagged,
    Setting,
    NotificationStaff,
)
from ora_backend.utils.auth import get_token_requester
from ora_backend.utils.query import (
    get_one_latest,
    get_flagged_chats_of_online_visitors,
    get_many,
    get_subscribed_staffs_for_visitor,
)
from ora_backend.utils.notifications import send_notifications_to_all_high_ups
from ora_backend.utils.serialization import serialize_to_dict
from ora_backend.utils.settings import get_settings_from_cache
from ora_backend.utils.permissions import role_is_authorized
from ora_backend.utils.assign import auto_assign_staff_to_chat


mode = _environ.get("MODE", "development").lower()
if mode == "production":
    # Internally, socketio.AsyncRedisManager uses `aioredis`
    mgr = socketio.AsyncRedisManager(
        "redis://:{}@127.0.0.1:6379/0".format(_environ.get("DB_PASSWORD"))
    )
    sio = socketio.AsyncServer(
        async_mode="sanic",
        cors_allowed_origins=[],
        client_manager=mgr,
        cors_credentials=True,
        ping_timeout=30,  # in seconds
        ping_interval=15,
    )
elif mode == "testing":
    sio = socketio.AsyncServer(
        async_mode="sanic", cors_allowed_origins=[], cors_credentials=True
    )
else:
    sio = socketio.AsyncServer(
        async_mode="sanic",
        cors_allowed_origins=[],
        cors_credentials=True,
        logger=True,
        engineio_logger=True,
    )
sio.attach(app)


def is_chat_room(room_id: str):
    return not room_id.startswith(UNCLAIMED_CHATS_PREFIX)


async def authenticate_user(environ: dict):
    if "HTTP_AUTHORIZATION" not in environ:
        raise ConnectionRefusedError("Authentication fails")

    token = environ["HTTP_AUTHORIZATION"].replace("Bearer ", "")
    try:
        user = await get_token_requester(token)
    except (JWTExtendedException, Unauthorized):
        raise ConnectionRefusedError("Authentication fails")
    except ExpiredSignatureError:
        raise ConnectionRefusedError("Token has expired")

    user_type = Visitor.__tablename__
    try:
        if "name" in user:  # Is visitor
            user = await Visitor.get(id=user["id"])
        else:
            user = await User.get(id=user["id"])
            user_type = User.__tablename__
    except NotFound:
        raise ConnectionRefusedError("Authentication fails")
    return user, user_type


async def get_sequence_num_for_visitor(user_id: str):
    visitor_info = await cache.get(user_id, {}, namespace="visitor_info")
    if not visitor_info:
        return False, {}, "The chat room is either closed or doesn't exist."

    chat_room_info = visitor_info.get("room")
    sequence_num = chat_room_info.get("sequence_num", 0)

    visitor_info["room"]["sequence_num"] = sequence_num + 1
    await cache.set(user_id, visitor_info, namespace="visitor_info")

    return sequence_num, visitor_info, None


# async def auto_assign_staff_to_chat(visitor_id, exclude_staff_id=None):
#     # If the setting for auto-assign is off, return None
#     settings = await cache.get(CACHE_SETTINGS, namespace="settings")
#     if not settings.get("auto_assign", 1):
#         return None
#
#     all_volunteers = await cache.get("all_volunteers", namespace="staffs")
#     if not all_volunteers:
#         raw_volunteers = await User.query.where(
#             User.role_id == ROLES.inverse["agent"]
#         ).gino.all()
#         volunteers = [serialize_to_dict(user) for user in raw_volunteers]
#         counter = 0
#         staff = volunteers[0]
#         while staff["id"] == exclude_staff_id:
#             counter += 1
#             staff = volunteers[counter]
#         await cache.set(
#             "all_volunteers",
#             {"counter": counter + 1, "staffs": volunteers},
#             namespace="staffs",
#         )
#     else:
#         counter = all_volunteers["counter"]
#         if counter >= len(all_volunteers["staffs"]):
#             counter = 0
#         staff = all_volunteers[counter]
#         while staff["id"] == exclude_staff_id:
#             counter += 1
#             if counter >= len(all_volunteers["staffs"]):
#                 counter = 0
#             staff = all_volunteers[counter]
#         await cache.set(
#             "all_volunteers",
#             {"counter": counter + 1, "staffs": all_volunteers["staffs"]},
#             namespace="staffs",
#         )
#
#     # Assign the chat to the staff
#     if staff:
#         await StaffSubscriptionChat.add_if_not_exists(
#             staff_id=staff["id"], visitor_id=visitor_id
#         )
#     return staff


async def get_or_create_visitor_session(
    visitor_id: str, visitor: dict = None, chat_room: dict = None
):
    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if visitor_info:
        return visitor_info

    if not chat_room:
        chat_room = await Chat.get_or_create(visitor_id=visitor_id)

    if not visitor:
        visitor = await Visitor.get(id=visitor_id)

    latest_chat_msg = await get_one_latest(
        ChatMessage, chat_id=chat_room["id"], order_by="sequence_num"
    )
    sequence_num = 0
    if latest_chat_msg:
        sequence_num = latest_chat_msg.sequence_num

    # chat_staff = await StaffSubscriptionChat.get(chat_id=chat_room["id"], many=True, limit=99)
    # chat_staff_ids = [item["staff_id"] for item in chat_staff]
    # staffs = await User.get(
    #     many=True, in_column="id", in_values=chat_staff_ids, limit=99
    # )
    # staffs = dict(map(lambda staff: (staff["id"], staff), staffs))
    subscribed_staffs = await get_subscribed_staffs_for_visitor(visitor_id)
    staffs = {staff["id"]: staff for staff in subscribed_staffs}
    if not staffs:
        staff = await auto_assign_staff_to_chat(visitor_id)

    data = {
        "user": visitor,
        "type": Visitor.__tablename__,
        "room": {
            **chat_room,
            # "staffs": [],
            "staffs": staffs,
            "sequence_num": sequence_num + 1,
        },
    }
    await cache.set(visitor_id, data, namespace="visitor_info")

    return data


async def add_staff_to_chat_if_possible(staff_id, visitor_id, visitor_info):
    room = visitor_info["room"]["id"]
    staffs = visitor_info["room"].get("staffs", {})

    # Only add if the max staffs in a chat isnt reached
    settings = await get_settings_from_cache()
    max_staffs_in_chat = settings.get("max_staffs_in_chat", 0)

    if len(staffs) < max_staffs_in_chat:
        staff = await User.get(id=staff_id)

        visitor_info["room"].setdefault("staffs", {})[staff["id"]] = staff
        await StaffSubscriptionChat.add_if_not_exists(
            staff_id=staff_id, visitor_id=visitor_id
        )

        # Let everyone in the chat know a staff has been added
        await sio.emit("staff_being_added_to_chat", {"staff": staff}, room=room)
        return True, None, visitor_info

    return False, "The number of staffs in the room has reached the max capacity.", None


async def remove_staff_from_chat_if_possible(staff_id, visitor_id, visitor_info):
    room = visitor_info["room"]["id"]
    staff = await User.get(id=staff_id)

    visitor_info["room"].setdefault("staffs", {}).pop(staff["id"], None)
    await StaffSubscriptionChat.remove_if_exists(
        staff_id=staff_id, visitor_id=visitor_id
    )

    # Let everyone in the chat know a staff has been removed
    await sio.emit("staff_being_removed_from_chat", {"staff": staff}, room=room)
    return True, None, visitor_info


async def update_staffs_in_chat_if_possible(
    requester, new_staff_ids, visitor_id, visitor_info
):
    room = visitor_info["room"]["id"]
    current_staffs = visitor_info["room"].get("staffs", {})

    # If the staffs are the same, ignore
    new_staff_ids = set(new_staff_ids)
    cur_staff_ids = set(current_staffs.keys())
    if new_staff_ids == cur_staff_ids:
        return True, None, visitor_info, False

    # Only add if the max staffs in a chat isnt reached
    settings = await get_settings_from_cache()
    max_staffs_in_chat = settings.get("max_staffs_in_chat", 0)
    if len(new_staff_ids) > max_staffs_in_chat:
        return (
            False,
            "The number of staffs in the room has reached the max capacity.",
            None,
        )

    # Remove the old staffs
    for cur_staff_id in list(current_staffs.keys()):
        if cur_staff_id not in new_staff_ids:
            await StaffSubscriptionChat.remove_if_exists(
                staff_id=cur_staff_id, visitor_id=visitor_id
            )
            await sio.emit(
                "staff_being_removed_from_chat",
                {"staff": current_staffs[cur_staff_id]},
                room=room,
            )
            visitor_info["room"].setdefault("staffs", {}).pop(cur_staff_id, None)

            # Send a notification to the staff
            await NotificationStaff.add(
                staff_id=cur_staff_id,
                content={
                    "content": "You have been removed from the chat with {}, by {}".format(
                        visitor_info["user"]["name"], requester["full_name"]
                    )
                },
            )
    # Subscribe new staffs
    for new_staff_id in new_staff_ids:
        if new_staff_id not in current_staffs:
            staff = await User.get(id=new_staff_id)

            visitor_info["room"].setdefault("staffs", {})[staff["id"]] = staff
            await StaffSubscriptionChat.add_if_not_exists(
                staff_id=new_staff_id, visitor_id=visitor_id
            )

            # Let everyone in the chat know a staff has been added
            await sio.emit("staff_being_added_to_chat", {"staff": staff}, room=room)

            # Send a notification to staff
            await NotificationStaff.add(
                staff_id=new_staff_id,
                content={
                    "content": "You have been assigned to talk to {}, by {}".format(
                        visitor_info["user"]["name"], requester["full_name"]
                    )
                },
            )

    return True, None, visitor_info, True


# Socket.io events


@sio.event
async def connect(sid, environ: dict):
    user, user_type = await authenticate_user(environ)
    online_visitors_room = ONLINE_VISITORS_PREFIX
    online_users_room = ONLINE_USERS_PREFIX

    # Init app settings
    settings = await get_settings_from_cache()

    # Staff
    if user_type == User.__tablename__:
        org_id = UNCLAIMED_CHATS_PREFIX + user["organisation_id"]
        monitor_room = MONITOR_ROOM_PREFIX  # + user["organisation_id"]

        # Store the current online users
        onl_users = await cache.get(online_users_room, {})
        # if user["id"] not in onl_users:
        onl_users[user["id"]] = {**user, "sid": sid}
        await cache.set(online_users_room, onl_users)
        # else:
        #     await sio.emit("staff_already_online", data={"staff": user}, room=sid)
        #     return False, "The staff is already logged in."

        sio.enter_room(sid, org_id)

        # Update online user for other staffs
        await sio.emit(
            "staff_goes_online", data={"staff": user}, room=org_id, skip_sid=sid
        )

        # Logs the org_room to update events
        await sio.save_session(
            sid, {"user": user, "org_room": org_id, "monitor_room": monitor_room}
        )

        # If user is supervisor or admin, he could:
        # - Enter monitor room - whenever there is a new chat, the staff will be informed
        # - Enter all volunteers' chat rooms to monitor
        if user["role_id"] < ROLES.inverse["agent"]:
            sio.enter_room(sid, monitor_room)

        # Staff enters all subscribed room
        subscriptions = await StaffSubscriptionChat.query.where(
            StaffSubscriptionChat.staff_id == user["id"]
        ).gino.all()
        subscribed_visitors = {item.visitor_id for item in subscriptions}

        # Update the current unclaimed chats to the newly connected staff
        unclaimed_chats = {}
        if settings.get("allow_claiming_chat", 0):
            unclaimed_chats = await cache.get(org_id, {})

        online_visitors = await cache.get(online_visitors_room, {})

        # Get the flagged chats of online visitors
        # flagged_chats = []
        onl_visitor_ids = []
        if online_visitors:
            onl_visitor_ids = online_visitors.keys()
            # Inject the serving staff to the visitors
            current_chat_rooms = await cache.multi_get(
                onl_visitor_ids, namespace="visitor_info"
            )
            for visitor_id, chat_room in zip(onl_visitor_ids, current_chat_rooms):
                # online_visitors[visitor_id]["staff"] = (
                #     chat_room["room"].get("staff", 0) if chat_room else 0
                # )
                online_visitors[visitor_id]["staffs"] = (
                    chat_room["room"].get("staffs", {}) if chat_room else {}
                )
                # The staff joined the rooms he subscribed to
                if visitor_id in subscribed_visitors:
                    sio.enter_room(sid, chat_room["room"]["id"])

        # Get the offline unclaimed chats as well
        offline_unclaimed_chats = []
        if settings.get("allow_claiming_chat", 0):
            offline_unclaimed_chats_db = await get_many(ChatUnclaimed)
            off_unclaimed_visitor_ids = [
                item.visitor_id for item in offline_unclaimed_chats_db
            ]
            offline_unclaimed_chats_info = await Chat.get(
                many=True, in_column="visitor_id", in_values=off_unclaimed_visitor_ids
            )
            offline_unclaimed_chats_info_as_dict = {
                chat["visitor_id"]: chat for chat in offline_unclaimed_chats_info
            }
            offline_unclaimed_chats_visitor = await Visitor.get(
                many=True, in_column="id", in_values=off_unclaimed_visitor_ids
            )
            offline_unclaimed_chats_as_dict = {
                visitor["id"]: visitor for visitor in offline_unclaimed_chats_visitor
            }
            offline_unclaimed_chats = [
                {
                    **offline_unclaimed_chats_info_as_dict[visitor_id],
                    **offline_unclaimed_chats_as_dict[visitor_id],
                }
                for visitor_id in off_unclaimed_visitor_ids
            ]

        # Upon disconnection, the user session is deleted by socketio.
        # Storing the user sessions in cache to be used on disconnection.
        await cache.set(
            "user_{}".format(sid),
            {
                "user": user,
                "type": user_type,
                "org_room": org_id,
                "monitor_room": monitor_room,
                # "rooms": chat_staffs_visitors_ids + chat_staffs_unhandled_visitors_ids,
            },
        )

        await sio.emit(
            "staff_init",
            data={
                "unclaimed_chats": list(unclaimed_chats.values()),
                "offline_unclaimed_chats": offline_unclaimed_chats,
                # "flagged_chats": chat_flagged_visitors,
                "online_users": onl_users,
                "online_visitors": list(online_visitors.values()),
                # "active_chats": chat_staffs_visitors,
                # "active_chats_unhandled": chat_staffs_unhandled_visitors,
            },
            room=sid,
        )
    else:  # Visitor
        # Get/Create a chat room for each visitor
        chat_room = await Chat.get_or_create(visitor_id=user["id"])
        visitor_info = await get_or_create_visitor_session(
            user["id"], chat_room=chat_room
        )
        sio.enter_room(sid, chat_room["id"])
        await sio.save_session(sid, {"user": user, "room": chat_room})

        # This cache is used on visitor disconnection to remove caches and clean up rooms
        await cache.set(
            "user_{}".format(sid), {"user": user, "type": user_type, "room": chat_room}
        )

        # Mark the visitor as online
        onl_visitors = await cache.get(online_visitors_room, {})
        if user["id"] not in onl_visitors:
            onl_visitors[user["id"]] = {**user, "room": chat_room["id"]}
            await cache.set(online_visitors_room, onl_visitors)
        else:
            # If there are multiple tabs of the visitor
            await sio.emit(
                "visitor_room_exists",
                data={"visitor": {**visitor_info["room"], **visitor_info["user"]}},
                room=sid,
            )
            return False, "The chat room already exists."

        # Staff enters all subscribed room
        subscriptions = await StaffSubscriptionChat.query.where(
            StaffSubscriptionChat.visitor_id == user["id"]
        ).gino.all()
        subscribed_staffs = {item.staff_id for item in subscriptions}
        onl_users = await cache.get(online_users_room, {})
        for staff_id in subscribed_staffs:
            staff = onl_users.get(staff_id)
            if staff:
                sio.enter_room(staff["sid"], chat_room["id"])

        # Update the visitor's status as online
        # For now, there are no logic of choosing which orgs
        # And as there is only 1 org, choose it
        org = (await Organisation.query.gino.all())[0]
        org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
        await sio.emit(
            "visitor_goes_online",
            data={"visitor": {**visitor_info["room"], **visitor_info["user"]}},
            room=org_room,
            skip_sid=sid,
        )

        # Return the online staffs to visitor
        onl_users = await cache.get(online_users_room, {})

        # staff = visitor_info["room"].get("staff")
        staffs = visitor_info["room"].get("staffs")
        await sio.emit(
            "visitor_init",
            data={
                # "staff": staff if staff else None,
                "staffs": staffs if staffs else None,
                "online_staffs": onl_users,
            },
            room=sid,
        )

    return True, None


@sio.event
async def user_typing_send(sid, data):
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    visitor_id = data["visitor"]
    visitor_info = await cache.get(visitor_id, {}, namespace="visitor_info")
    if not visitor_info:
        return False, "The visitor has gone offline"

    chat_room_id = visitor_info["room"]["id"]
    await sio.emit(
        "user_typing_receive",
        {"visitor": visitor_info["user"]},
        room=chat_room_id,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def user_stop_typing_send(sid, data):
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    visitor_id = data["visitor"]
    visitor_info = await cache.get(visitor_id, {}, namespace="visitor_info")
    if not visitor_info:
        return False, "The visitor has gone offline"

    chat_room_id = visitor_info["room"]["id"]
    await sio.emit(
        "user_stop_typing_receive",
        {"visitor": visitor_info["user"]},
        room=chat_room_id,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def staff_join(sid, data):
    # Validation
    # if "room" not in data or not isinstance(data["room"], str):
    #     return False, "Missing/Invalid field: room"

    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    session = await sio.get_session(sid)
    visitor_id = data["visitor"]
    user = session["user"]
    org_room = session["org_room"]
    monitor_room = session["monitor_room"]
    settings = await get_settings_from_cache()

    if settings.get("allow_claiming_chat", 1):
        # Remove the chat from unclaimed chats
        unclaimed_chats = await cache.get(org_room, {})
        visitor_contents = []
        is_offline_chat = True
        if visitor_id in unclaimed_chats:
            removed_unclaimed_chat = unclaimed_chats.pop(visitor_id, {})
            visitor_contents = removed_unclaimed_chat.get("contents", [])
            await cache.set(org_room, unclaimed_chats)

            # `unclaimed_chats` only contains chats of ONLINE visitors
            is_offline_chat = False

        # If the claimed chat is offline
        # return the next offline unclaimed chat and remove the claimed one from the queue in DB
        next_unclaimed_visitor = None
        chat_of_unclaimed_visitor = None
        if is_offline_chat:
            next_unclaimed_visitor_data = await get_many(
                ChatUnclaimed, offset=15, limit=1
            )
            # Only if there is an offline unclaimed chat
            if next_unclaimed_visitor_data:
                next_unclaimed_visitor_id = next_unclaimed_visitor_data[0].visitor_id
                next_unclaimed_visitor = await Visitor.get(id=next_unclaimed_visitor_id)
                chat_of_unclaimed_visitor = await Chat.get(
                    visitor_id=next_unclaimed_visitor_id
                )

            # Remove the chat from DB
            await ChatUnclaimed.remove_if_exists(visitor_id=visitor_id)

    # await StaffSubscriptionChat.add_if_not_exists(
    #     staff_id=user["id"], visitor_id=visitor_id
    # )

    visitor_info = await get_or_create_visitor_session(visitor_id)
    chat_room_info = visitor_info.get("room")
    status, error_msg, new_visitor_info = await add_staff_to_chat_if_possible(
        user["id"], visitor_id, visitor_info
    )
    if not status:
        return status, error_msg
    visitor_info = new_visitor_info

    # Remove from unhandled queue
    # ChatUnhandled.remove_if_exists(visitor_id=visitor_id)

    # Broadcast a message to remove the chat from the queue for other staffs
    await sio.emit(
        "staff_claim_chat",
        {
            "staff": user,
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
            "next_offline_unclaimed_visitor": {
                **chat_of_unclaimed_visitor,
                **next_unclaimed_visitor,
            }
            if next_unclaimed_visitor
            else None,
        },
        room=org_room,
        skip_sid=sid,
    )

    sio.enter_room(sid, chat_room_info["id"])

    # Announce all supervisors + admins about the new chat
    await sio.emit(
        "agent_new_chat",
        {
            "staff": user,
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
            "contents": visitor_contents,
        },
        room=monitor_room,
        skip_sid=sid,
    )

    # Get the sequence number, and store in memory DB
    sequence_num = chat_room_info.get("sequence_num", 0)
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    # visitor_info["room"]["staff"] = {**user, "sid": sid}
    visitor_info["room"]["staffs"][user["id"]] = {**user, "sid": sid}
    await cache.set(visitor_id, visitor_info, namespace="visitor_info")

    # Emit the msg before storing it in DB
    await sio.emit(
        "staff_join_room", {"staff": user}, room=chat_room_info["id"], skip_sid=sid
    )

    # Update the rooms the staff is in
    # user_info = await cache.get("user_{}".format(sid))
    # if not user_info:
    #     return False, "The user does not exist"
    # user_info["rooms"].append(visitor_id)
    # await cache.set("user_{}".format(sid), user_info)

    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        content={"content": "join room"},
        sender=user["id"],
        chat_id=chat_room_info["id"],
    )
    return True, None


@sio.event
async def add_staff_to_chat(sid, data):
    # Validation
    if "staff" not in data or not isinstance(data["staff"], str):
        return False, "Missing/Invalid field: staff"

    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    session = await sio.get_session(sid)
    staff_id = data["staff"]
    visitor_id = data["visitor"]
    user = session["user"]
    is_allowed = await role_is_authorized(user["role_id"], "add_agents_to_chat")
    if not is_allowed:
        return False, "You are not authorized to add staffs to a chat."

    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."

    status, error_msg, new_visitor_info = await add_staff_to_chat_if_possible(
        staff_id, visitor_id, visitor_info
    )
    if status:
        await cache.set(visitor_id, new_visitor_info, namespace="visitor_info")
        return status, None

    # Send a notification to staff
    await NotificationStaff.add(
        staff_id=staff_id,
        content={
            "content": "You have been assigned to talk to {}, by {}".format(
                new_visitor_info["user"]["name"], user["full_name"]
            )
        },
    )

    return status, error_msg


@sio.event
async def remove_staff_from_chat(sid, data):
    # Validation
    if "staff" not in data or not isinstance(data["staff"], str):
        return False, "Missing/Invalid field: staff"

    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    session = await sio.get_session(sid)
    staff_id = data["staff"]
    visitor_id = data["visitor"]
    user = session["user"]
    is_allowed = await role_is_authorized(user["role_id"], "add_agents_to_chat")
    if not is_allowed:
        return False, "You are not authorized to remove staffs from a chat."

    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."

    status, error_msg, new_visitor_info = await remove_staff_from_chat_if_possible(
        staff_id, visitor_id, visitor_info
    )
    if status:
        await cache.set(visitor_id, new_visitor_info, namespace="visitor_info")
        return status, None

    # Send a notification to staff
    await NotificationStaff.add(
        staff_id=staff_id,
        content={
            "content": "You have been removed from the chat with {}, by {}".format(
                new_visitor_info["user"]["name"], user["full_name"]
            )
        },
    )

    return status, error_msg


@sio.event
async def update_staffs_in_chat(sid, data):
    # Validation
    if (
        "staffs" not in data
        or not isinstance(data["staffs"], list)
        or any(not isinstance(item, str) for item in data["staffs"])
    ):
        return False, "Missing/Invalid field: staff"

    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    session = await sio.get_session(sid)
    staff_ids = data["staffs"]
    visitor_id = data["visitor"]
    user = session["user"]
    monitor_room = session["monitor_room"]

    is_allowed = await role_is_authorized(user["role_id"], "add_agents_to_chat")
    if not is_allowed:
        return False, "You are not authorized to remove staffs from a chat."

    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."

    status, error_msg, new_visitor_info, changed = await update_staffs_in_chat_if_possible(
        user, staff_ids, visitor_id, visitor_info
    )
    if status and changed:
        await cache.set(visitor_id, new_visitor_info, namespace="visitor_info")

        # Let the supervisors know about the change
        sio.emit(
            "staffs_in_chat_changed",
            {"visitor": {**visitor_info["room"], **visitor_info["user"]}},
            room=monitor_room,
            skip_sid=sid,
        )
        return status, None

    return status, error_msg


@sio.event
async def take_over_chat(sid, data):
    """A higher-up staff could take over a chat of a lower one."""
    # Validation
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    session = await sio.get_session(sid)
    visitor_id = data["visitor"]

    # onl_visitors = await cache.get(online_visitors_room, {})
    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."
    # room = onl_visitors.get(visitor_id, {}).get("room")

    chat_room_info = visitor_info["room"]
    room = chat_room_info["id"]
    requester = session["user"]
    monitor_room = session["monitor_room"]

    # Get the settings
    settings = await get_settings_from_cache()
    is_one_to_one = settings.get("is_one_to_one", False)

    if is_one_to_one:
        # Get current serving staff
        cur_staff = visitor_info["room"]["staffs"]

        if not cur_staff:
            return False, "Cannot take over an unclaimed chat."

        # Only higher-up staffs can take over a lower one
        if requester["role_id"] >= cur_staff[0]["role_id"]:
            return (
                False,
                "A {} cannot take over a chat from a {}.".format(
                    ROLES[requester["role_id"]], ROLES[cur_staff["role_id"]]
                ),
            )

        # Let the staff and visitor know he has been kicked out
        staff_sid = cur_staff["sid"]
        event_data = {
            "staff": requester,
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
        }
        await sio.emit("staff_being_taken_over_chat", event_data, room=room)
        # await sio.emit("staff_being_taken_over_chat", event_data, room=staff_sid)

        # Kick the current staff out of the room
        sio.leave_room(staff_sid, room)

        # Requester join room
        sio.enter_room(sid, room)

        # Update "staff" in cache for room
        sequence_num = chat_room_info.get("sequence_num", 0)
        visitor_info["room"]["sequence_num"] = sequence_num + 1
        visitor_info["room"]["staffs"][0] = {**requester, "sid": sid}
        await cache.set(visitor_id, visitor_info, namespace="visitor_info")

        # Update the rooms the staff is in
        # user_info = await cache.get("user_{}".format(staff_sid))
        # if user_info:
        #     for index, room in enumerate(user_info["rooms"]):
        #         if room == visitor_id:
        #             del user_info["rooms"][index]
        #             await cache.set("user_{}".format(sid), user_info)
        #             break

        # Save the chat message of staff being taken over
        await ChatMessage.add(
            sequence_num=sequence_num,
            type_id=0,
            content={"content": "take over room"},
            sender=requester["id"],
            chat_id=room,
        )

        # Broadcast to all supervisors/admins that this chat has been taken over
        await sio.emit(
            "staff_take_over_chat",
            {
                "staff": requester,
                "visitor": {**visitor_info["room"], **visitor_info["user"]},
            },
            room=monitor_room,
            skip_sid=sid,
        )
        return True, None

    # If the setting is one visitor - many staffs
    staffs = visitor_info["room"].get("staffs", [])
    if len(staffs) < settings.get("max_staffs_in_chat", 0):
        # Requester join room
        sio.enter_room(sid, room)

        # Update "staff" in cache for room
        sequence_num = chat_room_info.get("sequence_num", 0)
        visitor_info["room"]["sequence_num"] = sequence_num + 1
        visitor_info["room"].setdefault("staffs", []).append({**requester, "sid": sid})
        await cache.set(visitor_id, visitor_info, namespace="visitor_info")

        # Save the chat message of staff being taken over
        await ChatMessage.add(
            sequence_num=sequence_num,
            type_id=0,
            content={"content": "join room"},
            sender=requester["id"],
            chat_id=room,
        )
        return True, None

    return False, "The number of staffs in the room has reached the max capacity."


async def handle_visitor_msg(sid, content):
    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    # Get visitor info from session
    session = await sio.get_session(sid)
    chat_room = session["room"]
    user = session["user"]
    # Get the settings
    settings = await get_settings_from_cache()
    allow_claiming_chat = settings.get("allow_claiming_chat", False)

    # Get the sequence number, and store in memory DB
    visitor_info = await get_or_create_visitor_session(user["id"], chat_room=chat_room)
    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    await cache.set(user["id"], visitor_info, namespace="visitor_info")

    # Store the message before emitting it
    chat_msg = await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )
    await sio.emit(
        "visitor_send",
        {
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
            "content": chat_msg,
        },
        room=visitor_info["user"]["id"],
        skip_sid=sid,
    )
    # Add to unhandled queue
    await ChatUnhandled.add_if_not_exists(visitor_id=visitor_info["user"]["id"])

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    staffs = visitor_info["room"]["staffs"]
    # staffs = visitor_info["room"]["staffs"]

    # Append the user to the in-memory unclaimed chats
    # only if the visitor is online
    if allow_claiming_chat:
        unclaimed_chats = await cache.get(org_room, {})
        if not staffs:
            if user["id"] not in unclaimed_chats:
                # If the visitor already has an offline unclaimed chat
                # Delete it in DB and move it to online unclaimed chat
                await ChatUnclaimed.remove_if_exists(visitor_id=user["id"])

                data = {
                    "visitor": {**visitor_info["room"], **visitor_info["user"]},
                    "contents": [chat_msg],
                }
                unclaimed_chats[user["id"]] = data
                await cache.set(org_room, unclaimed_chats)

                # Let the staffs know about the conversion
                await sio.emit(
                    "remove_visitor_offline_chat",
                    data={"visitor": visitor_info["user"]},
                    room=org_room,
                )

                # Add the chat to unclaimed chats
                await sio.emit("append_unclaimed_chats", data, room=org_room)

            # If the visitor has no staff assigned, append the content to unclaimed
            elif not visitor_info["room"]["staffs"]:
                unclaimed_chats[user["id"]]["contents"].append(chat_msg)
                await cache.set(org_room, unclaimed_chats)
                # Emit to add the message to listening clients
                await sio.emit(
                    "visitor_unclaimed_msg",
                    {
                        "visitor": {**visitor_info["room"], **visitor_info["user"]},
                        "content": chat_msg,
                    },
                    room=org_room,
                )

    # Broadcast the message to all high-level staffs
    # else:
    #     orgs = map(lambda staff: staff.organisation_id, staffs)
    #     monitor_rooms = set(map(lambda org: MONITOR_ROOM_PREFIX, orgs))
    #     for monitor_room in monitor_rooms:
    await sio.emit(
        "new_visitor_msg_for_supervisor",
        {
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
            "content": chat_msg,
        },
        # room=monitor_room
        room=MONITOR_ROOM_PREFIX,
    )

    return True, None


@sio.event
async def visitor_first_msg(sid, content):
    return await handle_visitor_msg(sid, content)


@sio.event
async def visitor_msg_unclaimed(sid, content):
    """Client emits to send another message, while the chat is still unclaimed."""
    return await handle_visitor_msg(sid, content)


@sio.event
async def visitor_msg(sid, content):
    return await handle_visitor_msg(sid, content)


@sio.event
async def change_chat_priority(sid, data):
    # Validation
    # if "room" not in data or not isinstance(data["room"], str):
    #     return False, "Missing/Invalid field: room"
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"
    if "severity_level" not in data or not isinstance(data["severity_level"], int):
        return False, "Missing/Invalid field: severity_level"

    # Get visitor info from session
    session = await sio.get_session(sid)
    # room = data["room"]
    visitor_id = data["visitor"]
    flag_message = data.get("flag_message")
    user = session["user"]
    # visitor_info = await cache.get(visitor_id, {}, namespace="visitor_info")
    # if not visitor_info:
    #     return False, "The chat room is either closed or doesn't exist."
    visitor_info = await get_or_create_visitor_session(visitor_id)
    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1

    room = visitor_info["room"]

    # Broadcast the the flagged_chat to all high-level staffs
    staff_info = await cache.get("user_{}".format(sid))
    monitor_room = staff_info["monitor_room"]
    if data["severity_level"] > 0:
        await ChatFlagged.add_if_not_exists(
            visitor_id=visitor_info["user"]["id"], flag_message=flag_message
        )
        await send_notifications_to_all_high_ups(
            {
                "content": "{} has flagged a chat of visitor {}".format(
                    user["full_name"], visitor_info["user"]["name"]
                )
            }
        )
    else:
        await ChatFlagged.remove_if_exists(visitor_id=visitor_info["user"]["id"])

    # Update cache of the room
    # chat_room_info = await cache.get(room)
    visitor_info["room"]["severity_level"] = data["severity_level"]
    await cache.set(visitor_id, visitor_info, namespace="visitor_info")

    # Update the severity_level of the chat
    await Chat.modify({"id": room["id"]}, {"severity_level": data["severity_level"]})
    await sio.emit(
        "chat_has_changed_priority_for_supervisor",
        {
            "visitor": {
                **visitor_info["room"],
                **visitor_info["user"],
                "flag_message": flag_message,
            },
            "staff": user,
        },
        room=monitor_room,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def staff_handled_chat(sid, data):
    # Validation
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    # Get visitor info from session
    session = await sio.get_session(sid)
    # room = data["room"]
    visitor_id = data["visitor"]
    user = session["user"]

    # Remove from unhandled queue
    await ChatUnhandled.remove_if_exists(visitor_id=visitor_id)

    # Broadcast the message to all high-level staffs
    staff_info = await cache.get("user_{}".format(sid))
    monitor_room = staff_info["monitor_room"]

    # Get the sequence number, and store in memory DB
    visitor_info = await get_or_create_visitor_session(visitor_id)
    await sio.emit(
        "staff_handled_chat_for_supervisor",
        {"staff": user, "visitor": {**visitor_info["room"], **visitor_info["user"]}},
        room=monitor_room,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def staff_msg(sid, data):
    # Validation
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"
    if "content" not in data or not isinstance(data["content"], dict):
        return False, "Missing/Invalid field: content"

    # Get visitor info from session
    session = await sio.get_session(sid)
    # room = data["room"]
    visitor_id = data["visitor"]
    content = data["content"]
    user = session["user"]

    # Get the sequence number, and store in memory DB
    visitor_info = await get_or_create_visitor_session(visitor_id)
    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    await cache.set(user["id"], visitor_info, namespace="visitor_info")
    room = visitor_info["room"]

    # Store the message in DB before emitting it
    chat_msg = await ChatMessage.add(
        sequence_num=sequence_num,
        content=content,
        chat_id=room["id"],
        sender=user["id"],
    )
    await sio.emit(
        "staff_send",
        {"content": chat_msg, "staff": user, "visitor": {**visitor_info["user"]}},
        room=room["id"],
        skip_sid=sid,
    )

    # Remove from unhandled queue
    await ChatUnhandled.remove_if_exists(visitor_id=visitor_id)

    # Broadcast the message to all high-level staffs
    staff_info = await cache.get("user_{}".format(sid))
    monitor_room = staff_info["monitor_room"]
    await sio.emit(
        "new_staff_msg_for_supervisor",
        {
            "staff": user,
            "content": chat_msg,
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
        },
        room=monitor_room,
        skip_sid=sid,
    )

    return True, None


async def handle_staff_leave(sid, session, data):
    # Validation
    if "visitor" not in data or not isinstance(data["visitor"], str):
        return False, "Missing/Invalid field: visitor"

    visitor_id = data["visitor"]
    user = session["user"]

    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."

    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1

    # Remove assigned `staff` to room
    # staff = visitor_info["room"]["staff"]
    # visitor_info["room"]["staff"] = 0
    staff = visitor_info["room"]["staffs"].pop(user["id"], None)
    visitor = visitor_info["user"]

    # visitor_info["room"]["staffs"] = visitor_info["room"]["staffs"].copy()
    visitor_info["room"]["staffs"].pop(user["id"], None)

    await StaffSubscriptionChat.remove_if_exists(
        staff_id=user["id"], visitor_id=visitor_id
    )

    # If the visitor is also offline, close the room
    online_visitors_room = ONLINE_VISITORS_PREFIX
    onl_visitors = await cache.get(online_visitors_room, {})
    online_users_room = ONLINE_USERS_PREFIX
    onl_users = await cache.get(online_users_room, {})

    if visitor["id"] not in onl_visitors and all(
        staff["id"] not in onl_users for staff in visitor_info["room"]["staffs"]
    ):
        await cache.delete(visitor_id, namespace="visitor_info")
    else:
        await cache.set(visitor_id, visitor_info, namespace="visitor_info")

    # Update the rooms the staff is in
    # user_info = await cache.get("user_{}".format(sid))
    # if not user_info:
    #     return False, "The user does not exist"
    # for index, room in enumerate(user_info["rooms"]):
    #     if room == visitor_id:
    #         del user_info["rooms"][index]
    #         await cache.set("user_{}".format(sid), user_info)
    #         break

    # Emit the msg before storing it in DB
    room = visitor_info["room"]
    await sio.emit(
        "staff_leave", {"staff": session["user"]}, room=room["id"], skip_sid=sid
    )

    if not visitor_info["room"]["staffs"]:
        await sio.emit("no_staff_left", {}, room=room["id"], skip_sid=sid)

    # Broadcast the leaving msg to all high-level staffs
    if staff:
        staff_info = await cache.get("user_" + staff["sid"])
        monitor_room = staff_info["monitor_room"]
        await sio.emit(
            "staff_leave_chat_for_supervisor",
            {
                "staff": user,
                "visitor": {**visitor_info["room"], **visitor_info["user"]},
            },
            room=monitor_room,
        )

    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        sender=user["id"],
        content={"content": "leave room"},
        chat_id=room["id"],
    )

    return True, None


@sio.event
async def staff_leave_room(sid, data):
    session = await sio.get_session(sid)
    return await handle_staff_leave(sid, session, data)


async def handle_visitor_leave(sid, session, is_disconnected=False):
    room = session["room"]
    user = session["user"]

    # Remove the room from the queue if there is
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    visitor_info = await cache.get(user["id"], namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."

    # Remove the visitor from unclaimed chat
    unclaimed_chats = await cache.get(org_room, {})
    if user["id"] in unclaimed_chats:
        unclaimed_chats.pop(user["id"], None)
        await cache.set(org_room, unclaimed_chats)

        # Mark the chat as unclaimed in DB
        await ChatUnclaimed.add_if_not_exists(visitor_id=user["id"])

        # Let the staffs know a chat has changed from online to offline
        await sio.emit(
            "unclaimed_chat_to_offline",
            {"visitor": {**visitor_info["room"], **visitor_info["user"]}},
            room=org_room,
        )

    # Broadcast to high-level staffs to stop monitoring the chat
    staffs = visitor_info["room"]["staffs"]
    if staffs:
        monitor_room = MONITOR_ROOM_PREFIX
        await sio.emit(
            "visitor_leave_chat_for_supervisor",
            {"visitor": {**visitor_info["room"], **visitor_info["user"]}},
            room=monitor_room,
            skip_sid=sid,
        )

    if is_disconnected:
        sio.leave_room(sid, room["id"])
    else:
        # If the visitor leaves the chat himself, kick everyone out
        await sio.close_room(room["id"])
        sio.enter_room(sid, room["id"])

        # Annouce to all staffs that the visitor has left
        await sio.emit(
            "visitor_leave_queue",
            {"visitor": {**visitor_info["room"], **visitor_info["user"]}},
            room=org_room,
        )

    # The user is still online
    # if staffs and not is_disconnected:
    #     # Remove assigned `staff` in cache
    #     visitor_info["room"]["staffs"] = []
    #     await cache.set(user["id"], visitor_info, namespace="visitor_info")

    # If neither the visitor or no staffs is using the room
    online_users_room = ONLINE_USERS_PREFIX
    onl_users = await cache.get(online_users_room, {})

    if is_disconnected and all(
        staff["id"] not in onl_users for staff in visitor_info["room"]["staffs"]
    ):
        await cache.delete(user["id"], namespace="visitor_info")


@sio.event
async def visitor_leave_room(sid):
    session = await sio.get_session(sid)
    await handle_visitor_leave(sid, session)
    return True, None


@sio.event
async def disconnect_request(sid):
    await sio.disconnect(sid)


@sio.event
async def disconnect(sid):
    # session = await sio.get_session(sid)
    session = await cache.get("user_{}".format(sid))
    if not session:
        return False, "The user has already disconnected."

    # Visitor
    if session["type"] == Visitor.__tablename__:
        # room = session["room"]
        user = session["user"]

        # Remove the visitor from online visitors first
        # to avoid user re-connects before finishing processing
        online_visitors_room = ONLINE_VISITORS_PREFIX
        onl_visitors = await cache.get(online_visitors_room, {})
        onl_visitors.pop(user["id"], None)
        await cache.set(online_visitors_room, onl_visitors)

        # Process the post-disconnection
        await handle_visitor_leave(sid, session, is_disconnected=True)

        # Let the staff know the the visitor has gone offline
        # For now, there are no logic of choosing which orgs
        # And as there is only 1 org, choose it
        org = (await Organisation.query.gino.all())[0]
        org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
        await sio.emit(
            "visitor_goes_offline", data={"visitor": user}, room=org_room, skip_sid=sid
        )

    else:  # Staff
        # Update the current online staffs
        user = session["user"]
        online_users_room = ONLINE_USERS_PREFIX
        onl_users = await cache.get(online_users_room, {})
        if user["id"] in onl_users:
            onl_users.pop(user["id"], None)
            await cache.set(online_users_room, onl_users)

        org_room = session["org_room"]
        monitor_room = session["monitor_room"]
        # rooms = sio.rooms(sid)
        staff_info = await cache.get("user_{}".format(sid))
        if not staff_info:
            return False, "The user does not exist"
        # rooms = staff_info["rooms"]

        # Disconnect and close all chat rooms if a staff disconnects
        # Broadcast to org_room to let other staffs know this staff is offline
        # Update online user for other staffs
        await sio.emit(
            "staff_goes_offline",
            data={"staff": session["user"]},
            room=org_room,
            skip_sid=sid,
        )

        # Disconnect from queue room
        # org_room_id = org_room.replace(UNCLAIMED_CHATS_PREFIX, "")
        sio.leave_room(sid, org_room)
        sio.leave_room(sid, monitor_room)

    await cache.delete("user_{}".format(sid), {})
    return True, None
