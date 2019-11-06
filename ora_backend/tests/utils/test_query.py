from time import sleep
from pprint import pprint

from ora_backend.constants import DEFAULT_SEVERITY_LEVEL_OF_CHAT
from ora_backend.models import Visitor, Chat
from ora_backend.tests import get_fake_visitor, profile_created_from_origin
from ora_backend.utils.query import get_flagged_chats_of_online_visitors


async def test_get_flagged_chats_of_online_visitors(supervisor1_client):
    # Create some visitors
    visitors = []
    chats = []
    for _ in range(30):
        new_visitor = get_fake_visitor()
        new_visitor.pop("id")

        res = await supervisor1_client.post("/visitors", json=new_visitor)
        assert res.status == 200
        body = await res.json()
        visitors.append(body["data"])
        chat = await Chat.get_or_create(visitor_id=body["data"]["id"])
        chats.append(chat)

    # Flag some chats
    index = 7
    for visitor in visitors[7:26]:
        chat = await Chat.get_or_create(visitor_id=visitor["id"])
        sleep(0.001)
        updated_chat = await Chat.modify(
            {"id": chat["id"]}, {"severity_level": DEFAULT_SEVERITY_LEVEL_OF_CHAT + 1}
        )
        chats[index] = updated_chat
        index += 1

    # Get the first 15 flagged chats
    online_visitors = [visitor["id"] for visitor in visitors]
    flagged_chats = await get_flagged_chats_of_online_visitors(
        Visitor, Chat, in_values=online_visitors
    )
    assert len(flagged_chats) == 15
    for expected, flag_chat in zip(reversed(visitors[11:26]), flagged_chats):
        room = flag_chat["room"]
        visitor = flag_chat["visitor"]

        # Compare
        chat = await Chat.get(visitor_id=visitor["id"])
        assert profile_created_from_origin(room, chat)
        assert profile_created_from_origin(expected, visitor)

    # Unflag some chats
    for chat in chats[11:25]:
        await Chat.modify(
            {"id": chat["id"]}, {"severity_level": DEFAULT_SEVERITY_LEVEL_OF_CHAT}
        )

    # Get the remained flagged chats
    flagged_chats = await get_flagged_chats_of_online_visitors(
        Visitor, Chat, in_values=online_visitors
    )
    assert len(flagged_chats) == 5
    for expected, flag_chat in zip(
        reversed(visitors[7:11] + visitors[25:26]), flagged_chats
    ):
        room = flag_chat["room"]
        visitor = flag_chat["user"]

        # Compare
        chat = await Chat.get(visitor_id=visitor["id"])
        assert profile_created_from_origin(room, chat)
        assert profile_created_from_origin(expected, visitor)
