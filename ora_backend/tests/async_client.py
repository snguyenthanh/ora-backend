def create_async_client(sio):
    @sio.event
    async def staff_init(unclaimed_chats: list):
        """A list of unclaimed chats to show on front-end.

        Each chat in unclaimed_chats has the format:
        {
            "user": user, # The visitor
            "room": chat_room, # A Chat object. Refers to models.Chat for more info
            "contents": [content] # A list of `ChatMessage.content`, format decided by frontend
        }
        """
        # assert returned list == the one in cache

    @sio.event
    async def staff_claim_chat(data: dict):
        """
        Broadcast to queue room, to remove the unclaimed chat from others' clients.

        Args:
            data (dict):
                {"user": user, "room": room}
        """

    @sio.event
    async def staff_join_room(data: dict):
        """
        Emit to the visitor's room, to let him know a staff has joined.

        Args:
            data (dict):
                {"user": user} # The staff's info - models.User
        """
        # assert 2 ppl in chat room
        # assert "visitor" not in CACHE_UNCLAIMED_CHATS_PREFIX
        # Assert ChatMessage for staff joining

    @sio.event
    async def append_unclaimed_chats(data: dict):
        """
        Only register the visitor to queue room,
        when he submits the first message.

        Args:
            data (dict):
                {"user": user, "room": chat_room, "contents": [content]}
        """
        # assert CACHE_UNCLAIMED_CHATS_PREFIX has new chat
        # assert new ChatMessage

    @sio.event
    async def visitor_unclaimed_msg(data: dict):
        """
        For staffs, this event is emitted if the visitor sends other messages
        after the first init one, and the chat is yet to be claimed.

        This is to update all the staffs of incoming messages from the visitorself.

        Args:
            data (dict):
                {"user": session["user"], "content": content}
        """
        # assert CACHE_UNCLAIMED_CHATS_PREFIX is updated with extra contents
        # assert ChatMessage

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
