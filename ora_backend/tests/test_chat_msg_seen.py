from copy import deepcopy

from ora_backend.models import Visitor, Chat, ChatMessage
from ora_backend.tests import (
    get_fake_visitor,
    profile_created_from_origin,
    fake,
    get_next_page_link,
)
from ora_backend.utils.crypto import hash_password


async def test_get_last_seen_message_of_staff(supervisor1_client):
    # Create a lot more visitors to test
    visitors = [get_fake_visitor() for _ in range(3)]
    for visitor in visitors:
        _visitor = deepcopy(visitor)

        # Anonymous users don't have passwords
        if "password" in _visitor:
            _visitor["password"] = hash_password(_visitor["password"])
        await Visitor(**_visitor).create()

    # Create some dummy chat messages
    created_at = 1
    chat_messages = {}
    for visitor in visitors[::-1]:
        chat = await Chat.add(visitor_id=visitor["id"])
        for sequence_num in range(4):
            content = {"content": fake.sentence(nb_words=10)}
            chat_msg = {
                "chat_id": chat["id"],
                "sequence_num": sequence_num,
                "content": content,
                "sender": None,
                "created_at": created_at,
            }
            created_at += 1
            created_msg = await ChatMessage.add(**chat_msg)
            chat_messages.setdefault(chat["id"], []).append(created_msg)

    # Get the last seen messages of unseen chats
    for chat_id in chat_messages:
        chat_info = await Chat.get(id=chat_id)
        res = await supervisor1_client.get(
            "/visitors/{}/last_seen".format(chat_info["visitor_id"])
        )
        assert res.status == 200
        body = await res.json()
        assert "data" in body
        assert isinstance(body["data"], dict)
        assert body["data"]["last_seen_msg_id"] is None


async def test_update_last_seen_message_of_staff(supervisor1_client):
    # Create a lot more visitors to test
    visitors = [get_fake_visitor() for _ in range(3)]
    for visitor in visitors:
        _visitor = deepcopy(visitor)

        # Anonymous users don't have passwords
        if "password" in _visitor:
            _visitor["password"] = hash_password(_visitor["password"])
        await Visitor(**_visitor).create()

    # Create some dummy chat messages
    created_at = 1
    chat_messages = {}
    for visitor in visitors[::-1]:
        chat = await Chat.add(visitor_id=visitor["id"])
        for sequence_num in range(4):
            content = {"content": fake.sentence(nb_words=10)}
            chat_msg = {
                "chat_id": chat["id"],
                "sequence_num": sequence_num,
                "content": content,
                "sender": None,
                "created_at": created_at,
            }
            created_at += 1
            created_msg = await ChatMessage.add(**chat_msg)
            chat_messages.setdefault(chat["id"], []).append(created_msg)

    for chat_id, value in chat_messages.items():
        chat = await Chat.get(id=chat_id)
        res = await supervisor1_client.patch(
            "/visitors/{}/last_seen".format(chat["visitor_id"]),
            json={"last_seen_msg_id": value[2]["id"]},
        )
        assert res.status == 200
        body = await res.json()
        assert "data" in body
        assert isinstance(body["data"], dict)
        assert body["data"]["last_seen_msg_id"] == value[2]["id"]
