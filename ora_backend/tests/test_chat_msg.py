from pprint import pprint
from random import randint
from pytest import raises

from ora_backend import cache, db
from ora_backend.constants import UNCLAIMED_CHATS_PREFIX
from ora_backend.models import Chat, ChatMessage, Organisation, Visitor, User
from ora_backend.utils.query import get_one
from ora_backend.tests import (
    profile_created_from_origin,
    fake,
    get_next_page_link,
    get_prev_page_link,
)


async def test_get_chat_messages_of_non_exist_visitor(visitor1_client):
    res = await visitor1_client.get("/visitors/{}/messages".format("9" * 32))
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]
    assert isinstance(body["links"], dict)
    assert not body["links"]


async def test_get_chat_messages_of_visitor_having_no_chat_messages(
    visitor1_client, visitors
):
    visitor_id = visitors[-1]["id"]

    res = await visitor1_client.get("/visitors/{}/messages".format(visitor_id))
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]
    assert isinstance(body["links"], dict)
    assert not body["links"]


async def test_get_chat_messages_as_agent(agent1_client, visitors, users):
    visitor_id = visitors[-1]["id"]

    # Create some dummy chat messages
    chat = await Chat.add(visitor_id=visitor_id)
    messages = []
    for sequence_num in range(1, 25):
        content = {"value": fake.sentence(nb_words=10)}
        sender = users[-6]["id"] if randint(0, 1) else None
        chat_msg = {
            "chat_id": chat["id"],
            "sequence_num": sequence_num,
            "content": content,
            "sender": sender,
        }
        await ChatMessage.add(**chat_msg)
        chat_msg["sender"] = users[-6] if sender else None
        messages.append(chat_msg)

    # Try getting the chat messages
    res = await agent1_client.get("/visitors/{}/messages".format(visitor_id))
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 15  # The limit

    for expected, actual in zip(messages[9:], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    # Ensure that getting the next messages work too
    prev_page_link = get_prev_page_link(body)
    res = await agent1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 9

    for expected, actual in zip(messages[:9], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    # Ensure that getting the next messages are empty
    prev_page_link = get_prev_page_link(body)
    res = await agent1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]
    assert isinstance(body["links"], dict)
    assert not body["links"]


async def test_get_chat_messages_as_supervisor(supervisor1_client, visitors, users):
    visitor_id = visitors[-1]["id"]

    # Create some dummy chat messages
    chat = await Chat.add(visitor_id=visitor_id)
    messages = []
    for sequence_num in range(1, 25):
        content = {"value": fake.sentence(nb_words=10)}
        sender = users[-6]["id"] if randint(0, 1) else None
        chat_msg = {
            "chat_id": chat["id"],
            "sequence_num": sequence_num,
            "content": content,
            "sender": sender,
        }
        await ChatMessage.add(**chat_msg)
        chat_msg["sender"] = users[-6] if sender else None
        messages.append(chat_msg)

    # Try getting the chat messages
    res = await supervisor1_client.get("/visitors/{}/messages".format(visitor_id))
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 15  # The limit

    for expected, actual in zip(messages[9:], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    # Ensure that getting the next messages work too
    prev_page_link = get_prev_page_link(body)
    res = await supervisor1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 9

    for expected, actual in zip(messages[:9], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    # Ensure that getting the next messages are empty
    prev_page_link = get_prev_page_link(body)
    res = await supervisor1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]
    assert isinstance(body["links"], dict)
    assert not body["links"]


async def test_get_chat_messages_as_visitor(visitor1_client, visitors, users):
    visitor_id = visitors[-1]["id"]

    # Create some dummy chat messages
    chat = await Chat.add(visitor_id=visitor_id)
    messages = []
    for sequence_num in range(1, 25):
        content = {"value": fake.sentence(nb_words=10)}
        sender = users[-6]["id"] if randint(0, 1) else None
        chat_msg = {
            "chat_id": chat["id"],
            "sequence_num": sequence_num,
            "content": content,
            "sender": sender,
        }
        await ChatMessage.add(**chat_msg)
        chat_msg["sender"] = users[-6] if sender else None
        messages.append(chat_msg)

    # Try getting the chat messages
    res = await visitor1_client.get("/visitors/{}/messages".format(visitor_id))
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 15  # The limit

    for expected, actual in zip(messages[9:], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    # Ensure that getting the next messages work too
    prev_page_link = get_prev_page_link(body)
    res = await visitor1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 9

    for expected, actual in zip(messages[:9], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    # Ensure that getting the next messages are empty
    prev_page_link = get_prev_page_link(body)
    res = await visitor1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]
    assert isinstance(body["links"], dict)
    assert not body["links"]


async def test_get_messages_unread(supervisor1_client, visitors, users):
    visitor_id = visitors[-1]["id"]

    # Create some dummy chat messages
    chat = await Chat.add(visitor_id=visitor_id)
    messages = []
    for sequence_num in range(1, 37):
        content = {"value": fake.sentence(nb_words=10)}
        sender = users[-6]["id"] if randint(0, 1) else None
        chat_msg = {
            "chat_id": chat["id"],
            "sequence_num": sequence_num,
            "content": content,
            "sender": sender,
        }
        created_msg = await ChatMessage.add(**chat_msg)
        created_msg["sender"] = users[-6] if sender else None
        messages.append(created_msg)

    # Update the last seen message
    res = await supervisor1_client.patch(
        "/visitors/{}/last_seen".format(visitor_id),
        json={"last_seen_msg_id": messages[24]["id"]},
    )
    assert res.status == 200

    # Get the chat messages from unread
    res = await supervisor1_client.get(
        "/visitors/{}/messages?starts_from_unread=true".format(visitor_id)
    )
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "links" in body and "next" in body["links"] and "prev" in body["links"]
    assert len(body["data"]) == 15
    for expected, actual in zip(messages[10:25], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    next_page_link = get_next_page_link(body)
    prev_page_link = get_prev_page_link(body)

    # Get the prev pages until no more
    res = await supervisor1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "links" in body and "next" in body["links"] and "prev" in body["links"]
    assert len(body["data"]) == 10
    for expected, actual in zip(messages[:10], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])

    prev_page_link = get_prev_page_link(body)
    res = await supervisor1_client.get(prev_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]

    # Get the next messages from unread til most recent
    res = await supervisor1_client.get(next_page_link)
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "links" in body and "next" in body["links"] and "prev" in body["links"]
    assert len(body["data"]) == 11
    for expected, actual in zip(messages[25:37], body["data"]):
        assert profile_created_from_origin(expected, actual, ignore={"sender"})
        assert profile_created_from_origin(expected["sender"], actual["sender"])
