"""
As python-socketio catch ALL exceptions and only `traceback.print_exception`,
pytest could not pick the exception and mark the test case as failedself.

Therefore, exceptions will be stored in `cache` and be checked in the test cases,
rather than being raised.
"""

from ora_backend import cache
from ora_backend.constants import UNCLAIMED_CHATS_PREFIX
from ora_backend.models import Organisation, Chat
from ora_backend.tests.fixtures import visitors


def create_async_client(sio):
    @sio.event
    async def staff_init(unclaimed_chats: list):
        """A list of unclaimed chats to show on front-end.

        The staff will receive a list of all unclaimed chats
        right after connecting to the server.

        Each chat in unclaimed_chats has the format:
        {
            "user": user, # The visitor
            "room": chat_room, # A Chat object. Refers to models.Chat for more info
            "contents": [content] # A list of `ChatMessage.content`, format decided by frontend
        }
        """
        # assert returned list == the one in cache
        org = (await Organisation.query.gino.all())[0]
        org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
        cached_unclaims = await cache.get(org_room, [])

        if cached_unclaims != unclaimed_chats:
            excs = await cache.get("exceptions", [])
            excs.append(
                {
                    "event": "staff_init",
                    "condition": "cached_unclaims != unclaimed_chats",
                }
            )
            await cache.set("exceptions", excs)

    @sio.event
    async def staff_claim_chat(data: dict):
        """
        Broadcast to queue room, to remove the unclaimed chat from others' clients.

        Args:
            data (dict):
                {"user": user, "room": room}
        """
        org = (await Organisation.query.gino.all())[0]
        org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
        unclaimed_chats = await cache.get(org_room)

        for chat in unclaimed_chats:
            if data["room"] == chat["room"]["id"]:
                excs = await cache.get("exceptions", [])
                excs.append(
                    {
                        "event": "staff_claim_chat",
                        "condition": """room["id"] == chat["room"]["id"]""",
                    }
                )
                await cache.set("exceptions", excs)

    @sio.event
    async def staff_join_room(data: dict):
        """
        Emit to the visitor's room, to let him know a staff has joined.

        Args:
            data (dict):
                {"user": user} # The staff's info - models.User
        """
        # assert 2 ppl in chat room
        chat = await Chat.get(visitor_id=visitors[-1]["id"])
        chat_room = await cache.get(chat["id"])

        if chat_room["staff"] != data["user"]:
            excs = await cache.get("exceptions", [])
            excs.append(
                {
                    "event": "staff_join_room",
                    "condition": """chat_room["staff"] != data["user"]""",
                }
            )
            await cache.set("exceptions", excs)

    @sio.event
    async def append_unclaimed_chats(data: dict):
        """
        Only register the visitor to queue room,
        when he submits the first message.

        Args:
            data (dict):
                {"user": user, "room": chat_room, "contents": [content]}
        """
        # assert UNCLAIMED_CHATS_PREFIX has new chat
        # assert new ChatMessage
        org = (await Organisation.query.gino.all())[0]
        org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)
        cached_unclaims = await cache.get(org_room)

        # Ensure the new chat has been added to unclaimed chats
        if cached_unclaims[-1] != data:
            excs = await cache.get("exceptions", [])
            excs.append(
                {
                    "event": "append_unclaimed_chats",
                    "condition": "cached_unclaims[-1] != data",
                }
            )
            await cache.set("exceptions", excs)

    @sio.event
    async def visitor_unclaimed_msg(data: dict):
        """
        For staffs, this event is emitted if the visitor sends other messages
        after the first init one, and the chat is yet to be claimed.

        This is to update all the staffs of incoming messages from the visitorself.

        Args:
            data (dict):
                {"user": user, "content": content}
        """
        # assert org_room is updated with new content
        # Get the rooms
        org = (await Organisation.query.gino.all())[0]
        org_room = "{}{}".format(UNCLAIMED_CHATS_PREFIX, org.id)

        unclaimed_chats = await cache.get(org_room)
        for chat in unclaimed_chats:
            if (
                chat["user"]["id"] == data["user"]["id"]
                and chat["contents"][-1] == data["content"]
            ):
                break
        else:  # If no such chat is found or the chat is not updated
            excs = await cache.get("exceptions", [])
            condition = (
                """chat["user"]["id"] == data["user"]["id"]"""
                if chat["user"]["id"] == data["user"]["id"]
                else """chat["contents"][-1] == data["content"]"""
            )
            excs.append({"event": "visitor_unclaimed_msg", "condition": condition})
            await cache.set("exceptions", excs)

    @sio.event
    async def visitor_send(data: dict):
        """
        For the staff serving the visitor to receive his messages.
        Args:
            data (dict):
                {"content": content}
        """
        # assert ChatMessage

    @sio.event
    async def staff_send(data: dict):
        """
        For the visitor to receive the messages from the serving staff in the room.

        Args:
            data (dict):
                {
                    "content": content,
                    "user": user    # The staff info, for front-end to display
                }
        """
        # assert ChatMessage

    @sio.event
    async def staff_leave(data: dict):
        """
        For the visitor to be notified about the staff having left the chat.

        Args:
            data (dict):
                {"user": user}  # The staff who left
        """
        # assert ChatMessage
        # assert room is closed
        # assert room is deleted from cache

    @sio.event
    async def visitor_leave(data: dict):
        """
        For staff to be notified which visitor has left the chat.

        Args:
            data (dict):
                {"user": user}  # The visitor who left
        """
        # assert ChatMessage
        # assert room is closed
        # assert room is deleted from cache

    return sio
