from os import environ
from pprint import pprint

import socketio
from socketio.exceptions import ConnectionRefusedError
from sanic.exceptions import Unauthorized
from sanic_jwt_extended.exceptions import JWTExtendedException

from ora_backend import app, cache
from ora_backend.constants import UNCLAIMED_CHATS_PREFIX
from ora_backend.models import Chat, ChatMessage, Organisation, Visitor, User
from ora_backend.utils.auth import get_token_requester
from ora_backend.utils.query import get_one_latest


mode = environ.get("MODE", "development").lower()
if mode == "production":
    mgr = socketio.AsyncRedisManager(
        "redis://:{}@127.0.0.1:6379/0".format(environ.get("DB_PASSWORD"))
    )
    sio = socketio.AsyncServer(
        async_mode="sanic", cors_allowed_origins=[], client_manager=mgr
    )
else:
    sio = socketio.AsyncServer(async_mode="sanic", cors_allowed_origins=[])
sio.attach(app)


async def authenticate_user(environ: dict):
    if "HTTP_AUTHORIZATION" not in environ:
        raise ConnectionRefusedError("Authentication fails")

    token = environ["HTTP_AUTHORIZATION"].replace("Bearer ", "")
    try:
        user = await get_token_requester(token)
    except (JWTExtendedException, Unauthorized):
        raise ConnectionRefusedError("Authentication fails")

    user_type = Visitor.__tablename__
    if "name" in user:  # Is visitor
        user = await Visitor.get(id=user["id"])
    else:
        user = await User.get(id=user["id"])
        user_type = User.__tablename__
    return user, user_type


async def get_sequence_num_for_room(room_id: str):
    chat_room_info = await cache.get(room_id, {})
    sequence_num = chat_room_info.get("sequence_num", 0)

    chat_room_info["sequence_num"] += 1
    await cache.set(room_id, chat_room_info)

    return sequence_num


# Ora events
@sio.event
async def connect(sid, environ: dict):
    user, user_type = await authenticate_user(environ)

    # Staff
    if user_type == User.__tablename__:
        org_id = UNCLAIMED_CHATS_PREFIX + user["organisation_id"]
        sio.enter_room(sid, org_id)
        await sio.save_session(sid, {"user": user, "org_room": org_id})
        await cache.set(
            "user_{}".format(sid), {"user": user, "type": user_type, "org_room": org_id}
        )

        # Update the current unclaimed chats to the newly connected staff
        unclaimed_chats = await cache.get(org_id, [])
        await sio.emit("staff_init", data=unclaimed_chats, room=sid)
    else:  # Visitor
        # Get/Create a chat room for each visitor
        chat_room = await Chat.get_or_create(visitor_id=user["id"])
        sio.enter_room(sid, chat_room["id"])
        await sio.save_session(sid, {"user": user, "room": chat_room})
        await cache.set(
            "user_{}".format(sid), {"user": user, "type": user_type, "room": chat_room}
        )

        # Inform the frontend the chat room info, to be forwarded by staffs
        # await sio.emit("visitor_init", {"room": chat_room}, room=chat_room["id"])

        # Update the sequence number of the chat
        latest_chat_msg = await get_one_latest(
            ChatMessage, chat_id=chat_room["id"], order_by="sequence_num"
        )
        sequence_num = 0
        if latest_chat_msg:
            sequence_num = latest_chat_msg.sequence_num
        await cache.set(
            chat_room["id"],
            {**chat_room, "staff": 0, "sequence_num": sequence_num + 1},
        )

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

    # If the chat is already claimed, reject the request
    chat_room_info = await cache.get(room, {})
    if not chat_room_info:
        return False, "The chat room is either closed or doesn't exist."

    if chat_room_info["staff"]:
        return False, "This chat is already claimed."

    # Remove the chat from unclaimed chats
    unclaimed_chats = await cache.get(org_room, [])
    for index, _chat in enumerate(unclaimed_chats):
        if _chat["room"]["id"] == room:
            del unclaimed_chats[index]
            break
    await cache.set(org_room, unclaimed_chats)

    # Broadcast a message to remove the chat from the queue for other staffs
    await sio.emit(
        "staff_claim_chat",
        {"user": user, "room": room},
        room=session["org_room"],
        skip_sid=sid,
    )

    sio.enter_room(sid, room)

    # Get the sequence number, and store in memory DB
    sequence_num = chat_room_info.get("sequence_num", 0)

    chat_room_info["sequence_num"] += 1
    chat_room_info["staff"] = user
    await cache.set(room, chat_room_info)

    # Emit the msg before storing it in DB
    await sio.emit("staff_join_room", {"user": user}, room=room, skip_sid=sid)
    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        content={"value": "join room"},
        sender=user["id"],
        chat_id=room,
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
    data = {"user": user, "room": chat_room, "contents": [content]}

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

    # Store the first the visitor sends
    sequence_num = await get_sequence_num_for_room(chat_room["id"])
    await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
    )
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
    sequence_num = chat_room_info.get("sequence_num", 1)
    await cache.set(chat_room["id"], {**chat_room_info, "sequence_num": sequence_num + 1})

    # For now, there are no logic of choosing which orgs
    # And as there is only 1 org, choose it
    org = (await Organisation.query.gino.all())[0]
    org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

    # Update the unclaimed chats
    unclaimed_chats = await cache.get(org_room, [])
    for _, _chat in enumerate(unclaimed_chats):
        if _chat["room"]["id"] == chat_room["id"]:
            _chat["contents"].append(content)
            break
    await cache.set(org_room, unclaimed_chats)

    # Emit to add the message to listening clients
    await sio.emit(
        "visitor_unclaimed_msg",
        {"user": session["user"], "content": content},
        room=org_room,
    )

    # Store the msg the visitor sends
    await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
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
    sequence_num = await get_sequence_num_for_room(chat_room["id"])

    # Emit the msg before storing it in DB
    await sio.emit(
        "visitor_send",
        {"user": visitor, "content": content},
        room=chat_room["id"],
        skip_sid=sid,
    )
    await ChatMessage.add(
        sequence_num=sequence_num, content=content, chat_id=chat_room["id"]
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
    sequence_num = await get_sequence_num_for_room(room)

    # Emit the msg before storing it in DB
    await sio.emit(
        "staff_send", {"content": content, "user": user}, room=room, skip_sid=sid
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
    sequence_num = await get_sequence_num_for_room(room)

    # Emit the msg before storing it in DB
    await sio.emit("staff_leave", {"user": session["user"]}, room=room, skip_sid=sid)
    await ChatMessage.add(
        sequence_num=sequence_num,
        type_id=0,
        sender=user["id"],
        content={"value": "leave room"},
        chat_id=room,
    )

    # When either the staff or visitor ends the chat, close the room
    await sio.close_room(room)
    await cache.delete(room)
    return True, None


@sio.event
async def staff_leave_room(sid, data):
    session = await sio.get_session(sid)
    return await handle_staff_leave(sid, session, data)


async def handle_visitor_leave(sid, session):
    room = session["room"]

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
            await sio.emit(
                "visitor_leave_queue", {"user": session["user"]}, room=org_room
            )
            break

    # Emit the msg before closing the room
    await sio.emit(
        "visitor_leave", {"user": session["user"]}, room=room["id"], skip_sid=sid
    )
    await sio.close_room(room["id"])
    await cache.delete(room["id"])


@sio.event
async def visitor_leave_room(sid, _):
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

    # Visitor
    if session["type"] == Visitor.__tablename__:
        await handle_visitor_leave(sid, session)
    else:  # Staff
        org_room = session["org_room"]
        rooms = sio.rooms(sid)

        # Disconnect and close all chat rooms if a staff disconnects
        for room in rooms:
            if room == sid:
                await sio.close_room(sid)
            elif room != org_room:
                await handle_staff_leave(sid, session, {"room": {"id": room}})

        # Disconnect from queue room
        org_room_id = org_room.replace(UNCLAIMED_CHATS_PREFIX, "")
        sio.leave_room(sid, org_room_id)

    await cache.delete("user_{}".format(sid), {})
    return True, None
