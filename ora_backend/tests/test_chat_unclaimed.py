from ora_backend.models import ChatUnclaimed


async def test_delete_offline_unclaimed_chat(visitors):
    # Create unclaimed chats
    for visitor in visitors:
        await ChatUnclaimed.add(visitor_id=visitor["id"])

    # Delete a few visitors
    for visitor in visitors[1:3]:
        await ChatUnclaimed.remove_if_exists(visitor_id=visitor["id"])

    all_unclaimed = await ChatUnclaimed.query.gino.all()
    assert len(all_unclaimed) == len(visitors[:1] + visitors[3:])
    for chat, visitor in zip(all_unclaimed, visitors[:1] + visitors[3:]):
        assert chat.visitor_id == visitor["id"]
