from os import environ as _environ
from pprint import pprint

import socketio
from socketio.exceptions import ConnectionRefusedError
from sanic.exceptions import Unauthorized
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
from ora_backend.models import Chat, ChatMessage, Organisation, Visitor, User
from ora_backend.utils.auth import get_token_requester
from ora_backend.utils.query import get_one_latest


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
    if "name" in user:  # Is visitor
        user = await Visitor.get(id=user["id"])
    else:
        user = await User.get(id=user["id"])
        user_type = User.__tablename__
    return user, user_type


async def get_sequence_num_for_room(room_id: str):
    chat_room_info = await cache.get(room_id, {})
    if not chat_room_info:
        return False, "The chat room is either closed or doesn't exist."

    sequence_num = chat_room_info.get("sequence_num", 0)

    chat_room_info["sequence_num"] += 1
    await cache.set(room_id, chat_room_info)

    return sequence_num, None


# Ora events
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
            "staff_goes_online", data={"user": user}, room=org_id, skip_sid=sid
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
            },
        )

        # Store the current online users
        onl_users = await cache.get(online_users_room, [])
        for index, _user in enumerate(onl_users):
            if _user["id"] == user["id"]:
                onl_users[index] = {**user, "sid": sid}
                break
        else:
            onl_users.append({**user, "sid": sid})
        await cache.set(online_users_room, onl_users)

        # If user is supervisor or admin, he could:
        # - Enter monitor room - whenever there is a new chat, the staff will be informed
        # - Enter all volunteers' chat rooms to monitor
        if user["role_id"] < ROLES.inverse["agent"]:
            sio.enter_room(sid, monitor_room)
            await boss_enter_agent_rooms(sid, onl_users)

        # Update the current unclaimed chats to the newly connected staff
        unclaimed_chats = await cache.get(org_id, [])
        online_visitors = await cache.get(online_visitors_room, [])
        await sio.emit(
            "staff_init",
            data={
                "unclaimed_chats": unclaimed_chats,
                "online_users": onl_users,
                "online_visitors": online_visitors,
            },
            room=sid,
        )
    else:  # Visitor
        # Get/Create a chat room for each visitor
        chat_room = await Chat.get_or_create(visitor_id=user["id"])
        sio.enter_room(sid, chat_room["id"])
        await sio.save_session(sid, {"user": user, "room": chat_room})
        await cache.set(
            "user_{}".format(sid), {"user": user, "type": user_type, "room": chat_room}
        )

        # Update the sequence number of the chat
        latest_chat_msg = await get_one_latest(
            ChatMessage, chat_id=chat_room["id"], order_by="sequence_num"
        )
        sequence_num = 0
        if latest_chat_msg:
            sequence_num = latest_chat_msg.sequence_num
        await cache.set(
            chat_room["id"], {**chat_room, "staff": 0, "sequence_num": sequence_num + 1}
        )

        # Mark the visitor as online
        onl_visitors = await cache.get(online_visitors_room, [])
        for visitor in onl_visitors:
            if visitor["id"] == user["id"]:
                break
        else:
            onl_visitors.append(user)
        await cache.set(online_visitors_room, onl_visitors)

    return True, None


@sio.event
async def staff_join(sid, data):
    # Validation
    if "room" not in data or not isinstance(data["room"], str):
        return False, "Missing/Invalid field: room"

    session = await sio.get_session(sid)
    room = data["room"]
    user = session["user"]
    org_room = session["org_room"]
    monitor_room = session["monitor_room"]

    chat_room_info = await cache.get(room, {})
    if not chat_room_info:
        return False, "The chat room is either closed or doesn't exist."

    # If the chat is already claimed, reject the request
    if chat_room_info["staff"]:
        return False, "This chat is already claimed."

    # Remove the chat from unclaimed chats
    unclaimed_chats = await cache.get(org_room, [])
    visitor_contents = []
    for index, _chat in enumerate(unclaimed_chats):
        if _chat["room"]["id"] == room:
            visitor_contents = _chat["contents"]
            del unclaimed_chats[index]
            break
    await cache.set(org_room, unclaimed_chats)

    # Broadcast a message to remove the chat from the queue for other staffs
    await sio.emit(
        "staff_claim_chat", {"user": user, "room": room}, room=org_room, skip_sid=sid
    )

    sio.enter_room(sid, room)

    # Announce all supervisors + admins about the new chat
    # Return the visitor's info
    chat_room_info = await Chat.get(id=room)
    visitor_info = await Visitor.get(id=chat_room_info["visitor_id"])
    await sio.emit(
        "agent_new_chat",
        {"user": user, "visitor": visitor_info, "contents": visitor_contents},
        room=monitor_room,
        skip_sid=sid,
    )

    # Get the sequence number, and store in memory DB
    sequence_num = chat_room_info.get("sequence_num", 0)

    chat_room_info["sequence_num"] += 1
    chat_room_info["staff"] = {**user, "sid": sid}
    await cache.set(room, chat_room_info)

    # Emit the msg before storing it in DB
    await sio.emit("staff_join_room", {"user": user}, room=room, skip_sid=sid)
    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        content={"content": "join room"},
        sender=user["id"],
        chat_id=room,
    )
    return True, None


@sio.event
async def take_over_chat(sid, data):
    """A higher-up staff could take over a chat of a lower one."""
    # Validation
    if "room" not in data or not isinstance(data["room"], str):
        return False, "Missing/Invalid field: room"

    session = await sio.get_session(sid)
    room = data["room"]
    requester = session["user"]
    monitor_room = session["monitor_room"]

    # Get current serving staff
    chat_room_info = await cache.get(room, {})
    if not chat_room_info:
        return False, "The chat room is either closed or doesn't exist."
    cur_staff = chat_room_info["staff"]

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
    await sio.emit("staff_being_taken_over_chat", {"user": requester}, room=room)

    # Kick the current staff out of the room
    staff_sid = cur_staff["sid"]
    sio.leave_room(staff_sid, room)

    # Requester join room
    sio.enter_room(sid, room)

    # Update "staff" in cache for room
    sequence_num = chat_room_info.get("sequence_num", 0)
    chat_room_info["sequence_num"] += 1
    chat_room_info["staff"] = {**requester, "sid": sid}
    await cache.set(room, chat_room_info)

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
        {"user": requester, "room": room},
        room=monitor_room,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def visitor_first_msg(sid, content):
    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    session = await sio.get_session(sid)
    chat_room = session["room"]
    user = session["user"]

    # Store the first msg the visitor sends
    sequence_num, error_msg = await get_sequence_num_for_room(chat_room["id"])
    if error_msg:
        return False, error_msg

    chat_msg = await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )
    data = {"user": user, "room": chat_room, "contents": [chat_msg]}

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    # Append the user to the in-memory unclaimed chats
    unclaimed_chats = await cache.get(org_room, [])
    for index, chat in enumerate(unclaimed_chats):
        if chat["user"]["id"] == user["id"]:
            unclaimed_chats[index] = data
            break
    else:
        unclaimed_chats.append(data)
    await cache.set(org_room, unclaimed_chats)

    # Add the chat to unclaimed chats
    await sio.emit("append_unclaimed_chats", data, room=org_room)

    return True, None


@sio.event
async def visitor_msg_unclaimed(sid, content):
    """Client emits to send another message, while the chat is still unclaimed."""
    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    session = await sio.get_session(sid)
    chat_room = session["room"]

    chat_room_info = await cache.get(chat_room["id"], {})
    if not chat_room_info:
        return False, "The chat room is either closed or doesn't exist."

    sequence_num = chat_room_info.get("sequence_num", 1)
    await cache.set(
        chat_room["id"], {**chat_room_info, "sequence_num": sequence_num + 1}
    )

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    # Store the msg the visitor sends
    chat_msg = await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )

    # Update the unclaimed chats
    unclaimed_chats = await cache.get(org_room, [])
    for _, _chat in enumerate(unclaimed_chats):
        if _chat["room"]["id"] == chat_room["id"]:
            _chat["contents"].append(chat_msg)
            break
    await cache.set(org_room, unclaimed_chats)

    # Emit to add the message to listening clients
    await sio.emit(
        "visitor_unclaimed_msg",
        {"user": session["user"], "content": content},
        room=org_room,
    )

    return True, None


@sio.event
async def visitor_msg(sid, content):
    # Validation
    if not content or not isinstance(content, dict):
        return False, "Missing/Invalid data"

    # Get visitor info from session
    session = await sio.get_session(sid)
    chat_room = session["room"]
    visitor = session["user"]

    # Get the sequence number, and store in memory DB
    sequence_num, error_msg = await get_sequence_num_for_room(chat_room["id"])
    if error_msg:
        return False, error_msg

    # Emit the msg before storing it in DB
    await sio.emit(
        "visitor_send",
        {"user": visitor, "content": content},
        room=chat_room["id"],
        skip_sid=sid,
    )

    # Broadcast the message to all high-level staffs
    room = await cache.get(chat_room["id"])
    staff = room["staff"]
    if staff:
        staff_info = await cache.get("user_" + staff["sid"])
        monitor_room = staff_info["monitor_room"]
        await sio.emit(
            "new_visitor_msg_for_supervisor",
            {"user": visitor, "content": content},
            room=monitor_room,
            skip_sid=sid,
        )

    await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )

    return True, None


@sio.event
async def change_chat_priority(sid, data):
    # Validation
    if "room" not in data or not isinstance(data["room"], str):
        return False, "Missing/Invalid field: room"
    if "severity_level" not in data or not isinstance(data["severity_level"], int):
        return False, "Missing/Invalid field: severity_level"

    # Get visitor info from session
    session = await sio.get_session(sid)
    room = data["room"]
    user = session["user"]

    # Broadcast the the flagged_chat to all high-level staffs
    staff_info = await cache.get("user_{}".format(sid))
    monitor_room = staff_info["monitor_room"]

    # Update the severity_level of the chat
    chat_room_info = await Chat.modify(
        {"id": room}, {"severity_level": data["severity_level"]}
    )
    await sio.emit(
        "chat_has_changed_priority_for_supervisor",
        {"room": chat_room_info, "user": user},
        room=monitor_room,
        skip_sid=sid,
    )

    return True, None


@sio.event
async def staff_msg(sid, data):
    # Validation
    if "room" not in data or not isinstance(data["room"], str):
        return False, "Missing/Invalid field: room"
    if "content" not in data or not isinstance(data["content"], dict):
        return False, "Missing/Invalid field: content"

    # Get visitor info from session
    session = await sio.get_session(sid)
    room = data["room"]
    content = data["content"]
    user = session["user"]

    # Get the sequence number, and store in memory DB
    sequence_num, error_msg = await get_sequence_num_for_room(room)
    if error_msg:
        return False, error_msg

    # Emit the msg before storing it in DB
    await sio.emit(
        "staff_send", {"content": content, "user": user}, room=room, skip_sid=sid
    )

    # Broadcast the message to all high-level staffs
    staff_info = await cache.get("user_{}".format(sid))
    monitor_room = staff_info["monitor_room"]
    await sio.emit(
        "new_staff_msg_for_supervisor",
        {"user": user, "content": content},
        room=monitor_room,
        skip_sid=sid,
    )

    await ChatMessage.add(
        sequence_num=sequence_num,
        content=data["content"],
        chat_id=room,
        sender=user["id"],
    )
    return True, None


async def handle_staff_leave(sid, session, data):
    # Validation
    if "room" not in data or not isinstance(data["room"], str):
        return False, "Missing/Invalid field: room"

    room = data["room"]
    user = session["user"]

    # Get the sequence number, and store in memory DB
    sequence_num, error_msg = await get_sequence_num_for_room(room)
    if error_msg:
        return False, error_msg

    # Emit the msg before storing it in DB
    await sio.emit("staff_leave", {"user": session["user"]}, room=room, skip_sid=sid)
    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        sender=user["id"],
        content={"content": "leave room"},
        chat_id=room,
    )

    # When either the staff or visitor ends the chat, close the room
    # await sio.close_room(room)
    # await cache.delete(room)

    # Remove assigned `staff` to room
    chat_room_info = await cache.get(room)
    staff = chat_room_info["staff"]
    chat_room_info["staff"] = 0
    await cache.set(room, chat_room_info)

    # Broadcast the leaving msg to all high-level staffs
    if staff:
        staff_info = await cache.get("user_" + staff["sid"])
        monitor_room = staff_info["monitor_room"]
        await sio.emit(
            "staff_leave_chat_for_supervisor",
            {"user": user},
            room=monitor_room,
            skip_sid=sid,
        )

    return True, None


@sio.event
async def staff_leave_room(sid, data):
    session = await sio.get_session(sid)
    return await handle_staff_leave(sid, session, data)


async def handle_visitor_leave(sid, session):
    room = session["room"]
    user = session["user"]

    # Remove the room from the queue if there is
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    # Append the user to the in-memory unclaimed chats
    unclaimed_chats = await cache.get(org_room, [])

    for index, _chat in enumerate(unclaimed_chats):
        if _chat["room"]["id"] == room["id"]:
            del unclaimed_chats[index]
            await cache.set(org_room, unclaimed_chats)

            # Annouce to the staffs that the room has been removed
            await sio.emit("visitor_leave_queue", {"user": user}, room=org_room)
            break

    # Broadcast to high-level staffs to stop monitoring the chat
    room = await cache.get(room["id"])
    staff = room["staff"]
    if staff:
        staff_info = await cache.get("user_" + staff["sid"])
        monitor_room = staff_info["monitor_room"]
        await sio.emit(
            "visitor_leave_chat_for_supervisor",
            {"user": user},
            room=monitor_room,
            skip_sid=sid,
        )

    # Emit the msg before closing the room
    await sio.emit(
        "visitor_leave", {"user": session["user"]}, room=room["id"], skip_sid=sid
    )
    await sio.close_room(room["id"])
    await cache.delete(room["id"])

    # Remove the visitor from cache
    online_visitors_room = ONLINE_VISITORS_PREFIX
    onl_visitors = await cache.get(online_visitors_room, [])
    for index, visitor in enumerate(onl_visitors):
        if visitor["id"] == user["id"]:
            del onl_visitors[index]
            break
    await cache.set(online_visitors_room, onl_visitors)


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
        await handle_visitor_leave(sid, session)
    else:  # Staff
        org_room = session["org_room"]
        monitor_room = session["monitor_room"]
        rooms = sio.rooms(sid)

        # Disconnect and close all chat rooms if a staff disconnects
        for room in rooms:
            # if room == sid:
            #     await sio.close_room(sid)
            if room not in [org_room, sid]:
                await handle_staff_leave(sid, session, {"room": room})

        # Broadcast to org_room to let other staffs know this staff is offline
        # Update online user for other staffs
        await sio.emit(
            "staff_goes_offline",
            data={"user": session["user"]},
            room=org_room,
            skip_sid=sid,
        )

        # Disconnect from queue room
        # org_room_id = org_room.replace(UNCLAIMED_CHATS_PREFIX, "")
        sio.leave_room(sid, org_room)
        sio.leave_room(sid, monitor_room)

        # Update the current online staffs
        user = session["user"]
        online_users_room = ONLINE_USERS_PREFIX + user["organisation_id"]
        onl_users = await cache.get(online_users_room, [])
        for index, _user in enumerate(onl_users):
            if _user["id"] == user["id"]:
                del onl_users[index]
                break
        await cache.set(online_users_room, onl_users)

    await cache.delete("user_{}".format(sid), {})
    return True, None
