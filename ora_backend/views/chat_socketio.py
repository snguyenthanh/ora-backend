from os import environ as _environ
from pprint import pprint

import socketio
from socketio.exceptions import ConnectionRefusedError
from sanic.exceptions import Unauthorized, NotFound
from sanic_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import ExpiredSignatureError

from ora_backend import app, cache
from ora_backend.constants import (
    UNCLAIMED_CHATS_PREFIX,
    ONLINE_USERS_PREFIX,
    ROLES,
    MONITOR_ROOM_PREFIX,
    ONLINE_VISITORS_PREFIX,
)
from ora_backend.models import (
    Chat,
    ChatMessage,
    Organisation,
    Visitor,
    User,
    ChatUnclaimed,
)
from ora_backend.utils.auth import get_token_requester
from ora_backend.utils.query import (
    get_one_latest,
    get_flagged_chats_of_online_visitors,
    get_many,
)


mode = _environ.get("MODE", "development").lower()
if mode == "production":
    # Internally, socketio.AsyncRedisManager uses `aioredis`
    mgr = socketio.AsyncRedisManager(
        "redis://:{}@127.0.0.1:6379/0".format(_environ.get("DB_PASSWORD"))
    )
    sio = socketio.AsyncServer(
        async_mode="sanic", cors_allowed_origins=[], client_manager=mgr
    )
elif mode == "testing":
    sio = socketio.AsyncServer(async_mode="sanic", cors_allowed_origins=[])
else:
    sio = socketio.AsyncServer(
        async_mode="sanic", cors_allowed_origins=[], logger=True, engineio_logger=True
    )
sio.attach(app)


def is_chat_room(room_id: str):
    return not room_id.startswith(UNCLAIMED_CHATS_PREFIX)


async def boss_enter_agent_rooms(boss_sid: str, agents: list):
    for _user in agents:
        if _user["role_id"] >= ROLES.inverse["agent"]:
            rooms = sio.rooms(_user["sid"])
            for room in rooms:
                if room != _user["sid"] and is_chat_room(room):
                    sio.enter_room(boss_sid, room)


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

    data = {
        "user": visitor,
        "type": Visitor.__tablename__,
        "room": {**chat_room, "staff": 0, "sequence_num": sequence_num + 1},
    }
    await cache.set(visitor_id, data, namespace="visitor_info")

    return data


# Socket.io events


@sio.event
async def connect(sid, environ: dict):
    user, user_type = await authenticate_user(environ)
    online_visitors_room = ONLINE_VISITORS_PREFIX

    # Staff
    if user_type == User.__tablename__:
        org_id = UNCLAIMED_CHATS_PREFIX + user["organisation_id"]
        online_users_room = ONLINE_USERS_PREFIX + user["organisation_id"]
        monitor_room = MONITOR_ROOM_PREFIX + user["organisation_id"]
        sio.enter_room(sid, org_id)

        # Update online user for other staffs
        await sio.emit(
            "staff_goes_online", data={"staff": user}, room=org_id, skip_sid=sid
        )

        # Logs the org_room to update events
        await sio.save_session(
            sid, {"user": user, "org_room": org_id, "monitor_room": monitor_room}
        )

        # Upon disconnection, the user session is deleted by socketio.
        # Storing the user sessions in cache to be used on disconnection.
        await cache.set(
            "user_{}".format(sid),
            {
                "user": user,
                "type": user_type,
                "org_room": org_id,
                "monitor_room": monitor_room,
                "rooms": [],
            },
        )

        # Store the current online users
        onl_users = await cache.get(online_users_room, {})
        if user["id"] not in onl_users:
            onl_users[user["id"]] = {**user, "sid": sid}
            await cache.set(online_users_room, onl_users)

        # If user is supervisor or admin, he could:
        # - Enter monitor room - whenever there is a new chat, the staff will be informed
        # - Enter all volunteers' chat rooms to monitor
        if user["role_id"] < ROLES.inverse["agent"]:
            sio.enter_room(sid, monitor_room)
            # await boss_enter_agent_rooms(sid, onl_users)

        # Update the current unclaimed chats to the newly connected staff
        unclaimed_chats = await cache.get(org_id, {})
        online_visitors = await cache.get(online_visitors_room, {})

        # Get the flagged chats of online visitors
        flagged_chats = []
        onl_visitor_ids = []
        if online_visitors:
            # onl_visitor_ids = [visitor["id"] for visitor in online_visitors]
            onl_visitor_ids = online_visitors.keys()
            flagged_chats = await get_flagged_chats_of_online_visitors(
                Visitor, Chat, in_values=onl_visitor_ids
            )

            # Inject the serving staff to the visitors
            # current_chat_room_ids = [
            #     visitor["room"] for visitor in online_visitors.values()
            # ]
            current_chat_rooms = await cache.multi_get(
                onl_visitor_ids, namespace="visitor_info"
            )
            for visitor_id, chat_room in zip(onl_visitor_ids, current_chat_rooms):
                online_visitors[visitor_id]["staff"] = (
                    chat_room["room"].get("staff", 0) if chat_room else 0
                )

        # Get the offline unclaimed chats as well
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

        await sio.emit(
            "staff_init",
            data={
                "unclaimed_chats": list(unclaimed_chats.values()),
                "offline_unclaimed_chats": offline_unclaimed_chats,
                "flagged_chats": flagged_chats,
                "online_users": onl_users,
                "online_visitors": list(online_visitors.values()),
            },
            room=sid,
        )
    else:  # Visitor
        # Get/Create a chat room for each visitor
        chat_room = await Chat.get_or_create(visitor_id=user["id"])

        # If the room already exists
        # existing_chat_room = await cache.get(chat_room["id"])
        # existing_visitor_info = await cache.get(user["id"], namespace="visitor_info")
        #
        # if existing_visitor_info:
        #     await sio.emit(
        #         "visitor_room_exists",
        #         data={
        #             "visitor": {
        #                 **existing_visitor_info["room"],
        #                 **existing_visitor_info["user"],
        #             }
        #         },
        #     )
        #     return False, "The chat room already exists."

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
            )
            return False, "The chat room already exists."

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

        staff = visitor_info["room"]["staff"]
        await sio.emit(
            "visitor_init", data={"staff": staff if staff else None}, room=sid
        )

        # Update the sequence number of the chat
        # If the room is not created
        # if not existing_visitor_info:
        # latest_chat_msg = await get_one_latest(
        #     ChatMessage, chat_id=chat_room["id"], order_by="sequence_num"
        # )
        # sequence_num = 0
        # if latest_chat_msg:
        #     sequence_num = latest_chat_msg.sequence_num
        # # await cache.set(
        # #     chat_room["id"], {**chat_room, "staff": 0, "sequence_num": sequence_num + 1}
        # # )
        # # This cache is used to direct the staffs to each visitor's room
        # await cache.set(
        #     user["id"],
        #     {
        #         "user": user,
        #         "type": user_type,
        #         "room": {**chat_room, "staff": 0, "sequence_num": sequence_num + 1},
        #     },
        #     namespace="visitor_info",
        # )

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
    # room = data["room"]
    user = session["user"]
    org_room = session["org_room"]
    monitor_room = session["monitor_room"]

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

    # visitor_info = await cache.get(visitor_id, {}, namespace="visitor_info")
    visitor_info = await get_or_create_visitor_session(visitor_id)
    if visitor_info["room"]["staff"]:
        return False, "This chat has already been claimed."
    # if not visitor_info:
    #     return False, "The chat room is either closed or doesn't exist."
    # visitor_info = await get_or_create_visitor_session(visitor_id)

    # # Mark the chat as claimed in DB
    # next_unclaimed

    # If the visitor is online
    # sequence_num = 0
    # if visitor_info:
    chat_room_info = visitor_info.get("room")
    # If the chat is already claimed, reject the request
    # if chat_room_info["staff"]:
    #     return False, "This chat is already claimed."

    # for index, _chat in enumerate(unclaimed_chats):
    #     if _chat["room"]["id"] == room:
    #         visitor_contents = _chat["contents"]
    #         del unclaimed_chats[index]
    #         break

    # If the claimed chat is offline
    # return the next offline unclaimed chat and remove the claimed one from the queue in DB
    next_unclaimed_visitor = None
    chat_of_unclaimed_visitor = None
    if is_offline_chat:
        next_unclaimed_visitor_data = await get_many(ChatUnclaimed, offset=15, limit=1)
        # Only if there is an offline unclaimed chat
        if next_unclaimed_visitor_data:
            next_unclaimed_visitor_id = next_unclaimed_visitor_data[0].visitor_id
            next_unclaimed_visitor = await Visitor.get(id=next_unclaimed_visitor_id)
            chat_of_unclaimed_visitor = await Chat.get(
                visitor_id=next_unclaimed_visitor_id
            )

        # Remove the chat from DB
        await ChatUnclaimed.remove_if_exists(visitor_id=visitor_id)

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
    # Return the visitor's info
    # chat_room_info = await Chat.get(id=room)
    # visitor_info = await Visitor.get(id=chat_room_info["visitor_id"])
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
    visitor_info["room"]["staff"] = {**user, "sid": sid}
    await cache.set(visitor_id, visitor_info, namespace="visitor_info")

    # Emit the msg before storing it in DB
    await sio.emit(
        "staff_join_room", {"staff": user}, room=chat_room_info["id"], skip_sid=sid
    )

    # Update the rooms the staff is in
    user_info = await cache.get("user_{}".format(sid))
    if not user_info:
        return False, "The user does not exist"
    user_info["rooms"].append(visitor_id)
    await cache.set("user_{}".format(sid), user_info)

    # else:   # If the visitor is offline
    #     # Broadcast a message to remove the chat from the queue for other staffs
    #     await sio.emit(
    #         "staff_claim_offline_chat",
    #         {"staff": user, "visitor_id": visitor_id},
    #         room=org_room,
    #         skip_sid=sid,
    #     )
    #
    #     # Store the join as a msg in DB
    #     chat_room_info = await Chat.get(visitor_id=visitor_id)
    #     latest_chat_msg = await get_one_latest(
    #         ChatMessage, chat_id=chat_room_info["id"], order_by="sequence_num"
    #     )
    #     sequence_num = 0
    #     if latest_chat_msg:
    #         sequence_num = latest_chat_msg.sequence_num

    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        content={"content": "join room"},
        sender=user["id"],
        chat_id=chat_room_info["id"],
    )
    return True, None


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
    # room = data["room"]
    # db_chat_room_info = await Chat.get(visitor_id=data["visitor"])
    # room = db_chat_room_info["id"]
    requester = session["user"]
    monitor_room = session["monitor_room"]

    # Get current serving staff
    cur_staff = visitor_info["room"]["staff"]

    if not cur_staff:
        return False, "Cannot take over an unclaimed chat."

    # Only higher-up staffs can take over a lower one
    if requester["role_id"] >= cur_staff["role_id"]:
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
    await sio.emit("staff_being_taken_over_chat", event_data, room=staff_sid)

    # Kick the current staff out of the room
    sio.leave_room(staff_sid, room)

    # Requester join room
    sio.enter_room(sid, room)

    # Update "staff" in cache for room
    sequence_num = chat_room_info.get("sequence_num", 0)
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    # chat_room_info["staff"] = {**requester, "sid": sid}
    visitor_info["room"]["staff"] = {**requester, "sid": sid}
    await cache.set(visitor_id, visitor_info, namespace="visitor_info")

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


async def handle_visitor_msg(sid, content):
    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    # Get visitor info from session
    session = await sio.get_session(sid)
    chat_room = session["room"]
    user = session["user"]

    # Get the sequence number, and store in memory DB
    # sequence_num, visitor_info, error_msg = await get_sequence_num_for_visitor(
    #     chat_room["id"]
    # )
    # if error_msg:
    #     return False, error_msg
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
        room=visitor_info["room"]["id"],
        skip_sid=sid,
    )

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    staff = visitor_info["room"]["staff"]

    # Append the user to the in-memory unclaimed chats
    # only if the visitor is online
    unclaimed_chats = await cache.get(org_room, {})
    if not staff:
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
        elif not visitor_info["room"]["staff"]:
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
    else:
        staff_info = await cache.get("user_" + staff["sid"])
        monitor_room = staff_info["monitor_room"]
        await sio.emit(
            "new_visitor_msg_for_supervisor",
            {
                "visitor": {**visitor_info["room"], **visitor_info["user"]},
                "content": chat_msg,
            },
            room=monitor_room,
            skip_sid=sid,
        )

    return True, None


@sio.event
async def visitor_first_msg(sid, content):
    return await handle_visitor_msg(sid, content)

    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    session = await sio.get_session(sid)
    if "room" not in session:
        return False, "The chat room is either closed or doesn't exist."
    chat_room = session["room"]

    # Only enter the chat room on first message
    sio.enter_room(sid, chat_room["id"])
    user = session["user"]

    # Store the first msg the visitor sends
    visitor_info = await get_or_create_visitor_session(user["id"], chat_room=chat_room)
    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    await cache.set(user["id"], visitor_info, namespace="visitor_info")

    # sequence_num, visitor_info, error_msg = await get_sequence_num_for_visitor(
    #     user["id"]
    # )
    # if error_msg:
    #     return False, error_msg

    chat_msg = await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )
    data = {
        "visitor": {**visitor_info["room"], **visitor_info["user"]},
        "contents": [chat_msg],
    }

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    # Append the user to the in-memory unclaimed chats
    unclaimed_chats = await cache.get(org_room, {})
    if user["id"] not in unclaimed_chats:
        unclaimed_chats[user["id"]] = data
        await cache.set(org_room, unclaimed_chats)

        # Add the chat to unclaimed chats
        await sio.emit("append_unclaimed_chats", data, room=org_room)

    # Mark the visitor as online
    online_visitors_room = ONLINE_VISITORS_PREFIX
    onl_visitors = await cache.get(online_visitors_room, {})
    if user["id"] not in onl_visitors:
        onl_visitors[user["id"]] = {**user, "room": chat_room["id"]}
        await cache.set(online_visitors_room, onl_visitors)

    return True, None


@sio.event
async def visitor_msg_unclaimed(sid, content):
    """Client emits to send another message, while the chat is still unclaimed."""
    return await handle_visitor_msg(sid, content)

    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    session = await sio.get_session(sid)
    chat_room = session["room"]
    user = session["user"]

    # visitor_info = await cache.get(user["id"], namespace="visitor_info")
    # if not visitor_info:
    #     return False, "The chat room is either closed or doesn't exist."
    visitor_info = await get_or_create_visitor_session(user["id"], chat_room=chat_room)
    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    await cache.set(user["id"], visitor_info, namespace="visitor_info")

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    # Store the msg the visitor sends
    chat_msg = await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )

    # Update the unclaimed chats
    unclaimed_chats = await cache.get(org_room, {})
    if user["id"] in unclaimed_chats:
        unclaimed_chats[user["id"]]["contents"].append(chat_msg)
        await cache.set(org_room, unclaimed_chats)
    # for _, _chat in enumerate(unclaimed_chats):
    #     if _chat["room"]["id"] == chat_room["id"]:
    #         _chat["contents"].append(chat_msg)
    #         break

    # Emit to add the message to listening clients
    await sio.emit(
        "visitor_unclaimed_msg",
        {
            "visitor": {**visitor_info["room"], **visitor_info["user"]},
            "content": chat_msg,
        },
        room=org_room,
    )

    return True, None


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

    # Update cache of the room
    # chat_room_info = await cache.get(room)
    visitor_info["room"]["severity_level"] = data["severity_level"]
    await cache.set(visitor_id, visitor_info, namespace="visitor_info")

    # Update the severity_level of the chat
    await Chat.modify({"id": room["id"]}, {"severity_level": data["severity_level"]})
    await sio.emit(
        "chat_has_changed_priority_for_supervisor",
        {"visitor": {**visitor_info["room"], **visitor_info["user"]}, "staff": user},
        room=monitor_room,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def staff_msg(sid, data):
    # Validation
    # if "room" not in data or not isinstance(data["room"], str):
    #     return False, "Missing/Invalid field: room"
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
    # sequence_num, visitor_info, error_msg = await get_sequence_num_for_visitor(
    #     visitor_id
    # )
    # if error_msg:
    #     return False, error_msg

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
        {"content": chat_msg, "staff": user},
        room=room["id"],
        skip_sid=sid,
    )

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

    # room = data["room"]
    visitor_id = data["visitor"]
    user = session["user"]

    # Get the sequence number, and store in memory DB
    # sequence_num, visitor_info, error_msg = await get_sequence_num_for_visitor(
    #     visitor_id
    # )
    # if error_msg:
    #     return False, error_msg

    visitor_info = await cache.get(visitor_id, namespace="visitor_info")
    if not visitor_info:
        return False, "The chat room is either closed or doesn't exist."

    sequence_num = visitor_info["room"]["sequence_num"]
    visitor_info["room"]["sequence_num"] = sequence_num + 1
    room = visitor_info["room"]

    # Emit the msg before storing it in DB
    await sio.emit(
        "staff_leave", {"staff": session["user"]}, room=room["id"], skip_sid=sid
    )
    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        sender=user["id"],
        content={"content": "leave room"},
        chat_id=room["id"],
    )

    # Remove assigned `staff` to room
    # chat_room_info = await cache.get(room)
    # chat_room_info = visitor_info["room"]
    # staff = chat_room_info["staff"]
    # chat_room_info["staff"] = 0
    staff = visitor_info["room"]["staff"]
    visitor_info["room"]["staff"] = 0
    visitor = visitor_info["user"]
    # try:
    #     visitor = await Visitor.get(id=chat_room_info["visitor_id"])
    # except NotFound:
    #     return False, "Unable to find the visitor."

    # Update the rooms the staff is in
    user_info = await cache.get("user_{}".format(sid))
    if not user_info:
        return False, "The user does not exist"
    for index, room in enumerate(user_info["rooms"]):
        if room == visitor_id:
            del user_info["rooms"][index]
            await cache.set("user_{}".format(sid), user_info)
            break

    # If the visitor is also offline, close the room
    online_visitors_room = ONLINE_VISITORS_PREFIX
    onl_visitors = await cache.get(online_visitors_room, {})
    if visitor["id"] not in onl_visitors:
        await cache.delete(visitor_id, namespace="visitor_info")
    else:
        await cache.set(visitor_id, visitor_info, namespace="visitor_info")

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

    # for index, _chat in enumerate(unclaimed_chats):
    #     if _chat["room"]["id"] == room["id"]:
    #         del unclaimed_chats[index]
    #         await cache.set(org_room, unclaimed_chats)
    #
    #         # Annouce to the staffs that the room has been removed
    #         await sio.emit("visitor_leave_queue", {"user": user}, room=org_room)
    #         break

    # room = await cache.get(room["id"])

    # Broadcast to high-level staffs to stop monitoring the chat
    staff = visitor_info["room"]["staff"]
    if staff:
        staff_info = await cache.get("user_" + staff["sid"])
        monitor_room = staff_info["monitor_room"]
        await sio.emit(
            "visitor_leave_chat_for_supervisor",
            {"visitor": {**visitor_info["room"], **visitor_info["user"]}},
            room=monitor_room,
            skip_sid=sid,
        )

    # Emit the msg before closing the room
    # await sio.emit(
    #     "visitor_leave", {"user": session["user"]}, room=room["id"], skip_sid=sid
    # )

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
    if staff and not is_disconnected:
        # Remove assigned `staff` in cache
        # chat_room_info = await cache.get(room["id"])
        # staff = chat_room_info["staff"]
        # chat_room_info["staff"] = 0
        visitor_info["room"]["staff"] = 0
        await cache.set(user["id"], visitor_info, namespace="visitor_info")

    # If neither the visitor or staff is using the room
    if not staff and is_disconnected:
        # await cache.delete(room["id"])
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
        # Remove the visitor from online visitors first
        # to avoid user re-connects before finishing processing
        online_visitors_room = ONLINE_VISITORS_PREFIX
        onl_visitors = await cache.get(online_visitors_room, {})
        onl_visitors.pop(user["id"], None)
        await cache.set(online_visitors_room, onl_visitors)

        # Process the post-disconnection
        await handle_visitor_leave(sid, session, is_disconnected=True)
        room = session["room"]
        user = session["user"]
        # await cache.delete(room["id"])

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
        online_users_room = ONLINE_USERS_PREFIX + user["organisation_id"]
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
        rooms = staff_info["rooms"]

        # Disconnect and close all chat rooms if a staff disconnects
        for room in rooms:
            # if room == sid:
            #     await sio.close_room(sid)
            if room not in [org_room, sid]:
                await handle_staff_leave(sid, session, {"visitor": room})

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
