from pprint import pprint

from ora_backend.models import Visitor, Chat, ChatMessage
from ora_backend.tests import (
    get_fake_visitor,
    profile_created_from_origin,
    fake,
    get_next_page_link,
)


async def test_get_unread_visitors_for_staff(supervisor1_client):
    # Create some visitors
    visitors = []
    for _ in range(30):
        new_visitor = get_fake_visitor()
        new_visitor.pop("id")

        res = await supervisor1_client.post("/visitors", json=new_visitor)
        assert res.status == 200
        body = await res.json()
        visitors.append(body["data"])

    # Create some dummy chat messages
    created_at = 1
    chat_messages = {}
    chats = []
    for visitor in visitors:
        chat = await Chat.add(visitor_id=visitor["id"])
        chats.append(chat)
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
            chat_messages.setdefault(visitor["id"], []).append(created_msg)

    # Mark some visitors as read
    for visitor in visitors[12:17] + visitors[22:26]:
        res = await supervisor1_client.patch(
            "/visitors/{}/last_seen".format(visitor["id"]),
            json={"last_seen_msg_id": chat_messages[visitor["id"]][-1]["id"]},
        )
        assert res.status == 200

    # Mark some visitors as partially read
    for visitor in visitors[5:10]:
        res = await supervisor1_client.patch(
            "/visitors/{}/last_seen".format(visitor["id"]),
            json={"last_seen_msg_id": chat_messages[visitor["id"]][2]["id"]},
        )
        assert res.status == 200

    # Get the first unread visitors
    res = await supervisor1_client.get("/visitors/unread")
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert "links" not in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 15
    for expected_visitor, expected_chat, item in zip(
        reversed(visitors[:12] + visitors[17:22] + visitors[26:]),
        reversed(chats[:12] + chats[17:22] + chats[26:]),
        body["data"],
    ):
        actual_visitor = item["user"]
        actual_chat = item["room"]
        assert profile_created_from_origin(expected_visitor, actual_visitor)
        assert profile_created_from_origin(expected_chat, actual_chat)

    # Mark some visitors as fully read
    for visitor in visitors[2:8] + visitors[26:29]:
        res = await supervisor1_client.patch(
            "/visitors/{}/last_seen".format(visitor["id"]),
            json={"last_seen_msg_id": chat_messages[visitor["id"]][3]["id"]},
        )
        assert res.status == 200

    # Get the second unread visitors
    res = await supervisor1_client.get("/visitors/unread")
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert "links" not in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 12
    for expected_visitor, expected_chat, item in zip(
        reversed(visitors[:2] + visitors[8:12] + visitors[17:22] + visitors[29:]),
        reversed(chats[:2] + chats[8:12] + chats[17:22] + chats[29:]),
        body["data"],
    ):
        actual_visitor = item["user"]
        actual_chat = item["room"]
        assert profile_created_from_origin(expected_visitor, actual_visitor)
        assert profile_created_from_origin(expected_chat, actual_chat)

    # Mark all visitors as read
    for visitor in visitors:
        res = await supervisor1_client.patch(
            "/visitors/{}/last_seen".format(visitor["id"]),
            json={"last_seen_msg_id": chat_messages[visitor["id"]][-1]["id"]},
        )
        assert res.status == 200

    # Get the last unread visitors
    res = await supervisor1_client.get("/visitors/unread")
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert "links" not in body
    assert isinstance(body["data"], list)
    assert not body["data"]
