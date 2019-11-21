import asyncio

from ora_backend import cache
from ora_backend.constants import CACHE_SETTINGS
from ora_backend.models import Setting
from ora_backend.utils.assign import auto_reassign_staff_to_chat
from ora_backend.utils.query import get_unhandled_visitors_with_no_replies
from ora_backend.utils.settings import get_latest_settings


async def check_for_reassign_chats_every_half_hour():
    while True:
        await asyncio.sleep(60 * 30)  # Seconds
        settings = await get_latest_settings()
        if not settings.get("auto_reassign", 1):
            continue

        max_waiting_hours = settings.get("hours_to_auto_reassign", 24)
        long_waited_visitors = await get_unhandled_visitors_with_no_replies(
            max_waiting_hours
        )

        for visitor in long_waited_visitors:
            await auto_reassign_staff_to_chat(visitor["id"])
