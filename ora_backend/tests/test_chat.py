from pprint import pprint
from unittest import mock

from pytest import raises
from socketio.exceptions import ConnectionError

from ora_backend import cache
from ora_backend.constants import UNCLAIMED_CHATS_PREFIX
from ora_backend.models import Chat, ChatMessage, Organisation, Visitor, User
from ora_backend.utils.query import get_one
from ora_backend.tests import profile_created_from_origin


async def test_visitor_start_chat_without_token(sio_client_visitor, server_path):
    # SocketIO raises ConnectionError on invalid/missing token
    with raises(ConnectionError):
        await sio_client_visitor.connect(server_path)

    with raises(ConnectionError):
        await sio_client_visitor.connect(
            server_path, headers={"Authorization": "Bearer 123.112.333"}
        )


async def test_visitor_join(sio_client_visitor, server_path, token_visitor_1, visitors):
    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )
    # A chat room is created when a visitor joins
    chat = await get_one(Chat, visitor_id=visitors[-1]["id"])
    assert chat is not None
    assert await cache.exists(chat.id)

    await sio_client_visitor.disconnect()

    # The chat room in cache is deleted when either of the visitor/staff leaves
    assert not await cache.exists(chat.id)


async def test_staff_join(sio_client_agent1, server_path, token_agent_1):
    await sio_client_agent1.connect(
        server_path, headers={"Authorization": token_agent_1}
    )
    await sio_client_agent1.disconnect()


async def test_visitor_send_first_msg(
    sio_client_visitor, server_path, token_visitor_1, visitors
):
    # Get the visitor info
    visitor = await Visitor.get(id=visitors[-1]["id"])

    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )
    chat = await get_one(Chat, visitor_id=visitor["id"])
    assert chat is not None
    assert await cache.exists(chat.id)

    # Get the queue room
    org = (await Organisation.query.gino.all())[0]
    queue_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats is None

    # Get the chat room
    chat_room = await Chat.get(visitor_id=visitor["id"])

    # Send the first message
    new_content = {"value": "This is the first message"}
    await sio_client_visitor.call("visitor_first_msg", new_content, timeout=1)

    # Ensure the cache has the sent message
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats == [
        {"user": visitor, "room": chat_room, "contents": [new_content]}
    ]

    # Check if the message has been updated to backend
    messages = await ChatMessage.get(chat_id=chat_room["id"])
    assert len(messages) == 1
    assert profile_created_from_origin(
        {
            "sequence_num": 1,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": new_content,
            "sender": None,
        },
        messages[0],
    )

    await sio_client_visitor.disconnect()


async def test_visitor_send_msg_before_a_staff_join(
    sio_client_visitor,
    server_path,
    token_visitor_1,
    sio_client_agent1,
    token_agent_1,
    visitors,
):
    # Get the visitor info
    visitor = await Visitor.get(id=visitors[-1]["id"])

    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )

    # Get the queue room
    org = (await Organisation.query.gino.all())[0]
    queue_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats is None

    # Get the chat room
    chat_room = await Chat.get(visitor_id=visitor["id"])

    # Send the first message
    new_content = {"value": "This is the first message"}
    await sio_client_visitor.call("visitor_first_msg", new_content)

    # A staff connects and receive the message
    await sio_client_agent1.connect(
        server_path, headers={"Authorization": token_agent_1}
    )
    await sio_client_agent1.sleep(1)

    # Assert no errors are raised when the staff connects
    excs = await cache.get("exceptions", [])
    assert not excs

    # Visitor sends another message (chat is still unclaimed)
    second_content = {"value": "Second message"}
    await sio_client_visitor.call("visitor_msg_unclaimed", second_content)

    # Check if the message has been updated to backend
    messages = await ChatMessage.get(chat_id=chat_room["id"])
    assert len(messages) == 2
    expected_msgs = [
        {
            "sequence_num": 1,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": new_content,
            "sender": None,
        },
        {
            "sequence_num": 2,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": second_content,
            "sender": None,
        },
    ]
    for expected, message in zip(expected_msgs, messages):
        assert profile_created_from_origin(expected, message)

    # Ensure that the chat in queue room is also updated
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats == [
        {"user": visitor, "room": chat_room, "contents": [new_content, second_content]}
    ]

    # Assert no errors are raised when the visitor sends the 2nd msg
    excs = await cache.get("exceptions", [])
    assert not excs

    await sio_client_visitor.disconnect()
    await sio_client_agent1.disconnect()


async def test_visitor_send_msg_after_a_staff_join(
    sio_client_visitor,
    server_path,
    token_visitor_1,
    sio_client_agent1,
    token_agent_1,
    visitors,
):
    # Get the visitor info
    visitor = await Visitor.get(id=visitors[-1]["id"])

    # Get the queue room
    org = (await Organisation.query.gino.all())[0]
    queue_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats is None

    # A staff connects first
    await sio_client_agent1.connect(
        server_path, headers={"Authorization": token_agent_1}
    )
    await sio_client_agent1.sleep(1)

    # Assert no errors are raised when the staff connects
    excs = await cache.get("exceptions", [])
    assert not excs

    # Then the visitor connects
    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )

    # Get the chat room
    chat_room = await Chat.get(visitor_id=visitor["id"])

    # Send the first message
    new_content = {"value": "This is the first message"}
    await sio_client_visitor.call("visitor_first_msg", new_content)

    # Assert no errors are raised when the first msg is sent
    excs = await cache.get("exceptions", [])
    assert not excs

    # Visitor sends another message (chat is still unclaimed)
    second_content = {"value": "Second message"}
    await sio_client_visitor.call("visitor_msg_unclaimed", second_content)

    # Assert no errors are raised when the 2nd msg is sent
    excs = await cache.get("exceptions", [])
    assert not excs

    # Check if the message has been updated to backend
    messages = await ChatMessage.get(chat_id=chat_room["id"])
    assert len(messages) == 2
    expected_msgs = [
        {
            "sequence_num": 1,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": new_content,
            "sender": None,
        },
        {
            "sequence_num": 2,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": second_content,
            "sender": None,
        },
    ]
    for expected, message in zip(expected_msgs, messages):
        assert profile_created_from_origin(expected, message)

    # Ensure that the chat in queue room is also updated
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats == [
        {"user": visitor, "room": chat_room, "contents": [new_content, second_content]}
    ]

    await sio_client_visitor.disconnect()
    await sio_client_agent1.disconnect()


async def test_staff_claim_a_visitor(
    sio_client_visitor,
    server_path,
    token_visitor_1,
    sio_client_agent1,
    token_agent_1,
    visitors,
    users,
):
    # Get the visitor info
    visitor = await Visitor.get(id=visitors[-1]["id"])
    agent = await User.get(id=users[-6]["id"])

    # Get the queue room
    org = (await Organisation.query.gino.all())[0]
    queue_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats is None

    # A staff connects first
    await sio_client_agent1.connect(
        server_path, headers={"Authorization": token_agent_1}
    )
    await sio_client_agent1.sleep(1)

    # Assert no errors are raised when the staff connects
    excs = await cache.get("exceptions", [])
    assert not excs

    # Then the visitor connects
    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )

    # Get the chat room
    chat_room = await Chat.get(visitor_id=visitor["id"])

    # Send the first message
    new_content = {"value": "This is the first message"}
    await sio_client_visitor.call("visitor_first_msg", new_content)

    # There are no staffs assigned yet
    cache_chat_room = await cache.get(chat_room["id"])
    assert cache_chat_room["staff"] is None

    # Staff claim the chat
    await sio_client_agent1.call("staff_join", {"room": chat_room["id"]}, timeout=1)

    # Assert no errors are raised when the staff claims the chat
    excs = await cache.get("exceptions", [])
    assert not excs

    # Ensure that the chat in queue room is also updated
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats == []

    # Staff sends a message
    staff_first_content = {"value": "I am an agent."}
    await sio_client_agent1.call(
        "staff_msg", {"room": chat_room["id"], "content": staff_first_content}
    )

    # Visitor sends back a message
    visitor_third_content = {"value": "Hello stranger."}
    await sio_client_visitor.call("visitor_msg", visitor_third_content, timeout=1)

    # Agent leaves the chat
    await sio_client_agent1.call("staff_leave_room", {"room": chat_room["id"]})

    messages = await ChatMessage.get(chat_id=chat_room["id"])
    assert len(messages) == 5
    expected_msgs = [
        {
            "sequence_num": 1,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": new_content,
            "sender": None,
        },
        {
            "sequence_num": 2,
            "type_id": 0,
            "content": {"value": "join room"},
            "sender": agent["id"],
            "chat_id": chat_room["id"],
        },
        {
            "sequence_num": 3,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": staff_first_content,
            "sender": agent["id"],
        },
        {
            "sequence_num": 4,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": visitor_third_content,
            "sender": None,
        },
        {
            "sequence_num": 5,
            "type_id": 0,
            "content": {"value": "leave room"},
            "sender": agent["id"],
            "chat_id": chat_room["id"],
        },
    ]
    for expected, message in zip(expected_msgs, messages):
        assert profile_created_from_origin(expected, message)

    await sio_client_visitor.disconnect()
    await sio_client_agent1.disconnect()


async def test_visitor_second_session(
    sio_client_visitor,
    server_path,
    token_visitor_1,
    sio_client_agent1,
    token_agent_1,
    visitors,
    users,
):
    # Get the visitor info
    visitor = await Visitor.get(id=visitors[-1]["id"])
    agent = await User.get(id=users[-6]["id"])

    # Get the queue room
    org = (await Organisation.query.gino.all())[0]
    queue_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
    unclaimed_chats = await cache.get(queue_room)
    assert unclaimed_chats is None

    # A staff connects first
    await sio_client_agent1.connect(
        server_path, headers={"Authorization": token_agent_1}
    )
    await sio_client_agent1.sleep(1)

    # Then the visitor connects
    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )

    # Get the chat room
    chat_room = await Chat.get(visitor_id=visitor["id"])

    # Send the first message
    new_content = {"value": "This is the first message"}
    await sio_client_visitor.call("visitor_first_msg", new_content)

    # Staff claim the chat
    await sio_client_agent1.call("staff_join", {"room": chat_room["id"]}, timeout=1)

    # Staff sends a message
    staff_first_content = {"value": "I am an agent."}
    await sio_client_agent1.call(
        "staff_msg", {"room": chat_room["id"], "content": staff_first_content}
    )

    # Visitor sends back a message
    visitor_third_content = {"value": "Hello stranger."}
    await sio_client_visitor.call("visitor_msg", visitor_third_content, timeout=1)

    # Agent leaves the chat
    await sio_client_agent1.call("staff_leave_room", {"room": chat_room["id"]})

    # Visitor disconnects to connect again, in a new session
    await sio_client_visitor.disconnect()

    # The room has been cleared from cache after visitor disconnects
    assert not await cache.exists(chat_room["id"])
    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )

    # Send a new message on the new session
    another_content = {"value": "First message in new session"}
    await sio_client_visitor.call("visitor_first_msg", another_content)

    messages = await ChatMessage.get(chat_id=chat_room["id"])
    assert len(messages) == 6
    expected_msgs = [
        {
            "sequence_num": 1,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": new_content,
            "sender": None,
        },
        {
            "sequence_num": 2,
            "type_id": 0,
            "content": {"value": "join room"},
            "sender": agent["id"],
            "chat_id": chat_room["id"],
        },
        {
            "sequence_num": 3,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": staff_first_content,
            "sender": agent["id"],
        },
        {
            "sequence_num": 4,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": visitor_third_content,
            "sender": None,
        },
        {
            "sequence_num": 5,
            "type_id": 0,
            "content": {"value": "leave room"},
            "sender": agent["id"],
            "chat_id": chat_room["id"],
        },
        {
            "sequence_num": 6,
            "chat_id": chat_room["id"],
            "type_id": 1,
            "content": another_content,
            "sender": None,
        },
    ]
    for expected, message in zip(expected_msgs, messages):
        assert profile_created_from_origin(expected, message)

    await sio_client_visitor.disconnect()
    await sio_client_agent1.disconnect()
