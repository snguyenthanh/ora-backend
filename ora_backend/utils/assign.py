from ora_backend import cache
from ora_backend.constants import CACHE_SETTINGS, ROLES
from ora_backend.models import User, StaffSubscriptionChat
from ora_backend.utils.query import delete_many
from ora_backend.utils.serialization import serialize_to_dict
from ora_backend.utils.settings import get_settings_from_cache


async def reset_all_volunteers_in_cache():
    raw_volunteers = await User.query.where(
        User.role_id == ROLES.inverse["agent"], User.disabled == False
    ).gino.all()
    volunteers = [serialize_to_dict(user) for user in raw_volunteers]
    volunteers_data = await cache.get("all_volunteers", namespace="staffs")
    if not volunteers_data:
        await cache.set(
            "all_volunteers", {"counter": 0, "staffs": volunteers}, namespace="staffs"
        )


async def auto_reassign_staff_to_chat(visitor_id):
    """Remove all the current subscribed staffs, and add a new one."""

    settings = await get_settings_from_cache()
    if not settings.get("auto_reassign", 1):
        return None

    raw_current_staffs = await StaffSubscriptionChat.query.where(
        StaffSubscriptionChat.visitor_id == visitor_id
    ).gino.all()
    current_staffs = {item.staff_id for item in raw_current_staffs}

    all_volunteers = await cache.get("all_volunteers", namespace="staffs")
    if not all_volunteers:
        raw_volunteers = await User.query.where(
            User.role_id == ROLES.inverse["agent"], User.disabled == False
        ).gino.all()
        volunteers = [serialize_to_dict(user) for user in raw_volunteers]
        counter = 0
        staff = volunteers[0]
        while staff["id"] in current_staffs:
            counter += 1
            staff = volunteers[counter]
        await cache.set(
            "all_volunteers",
            {"counter": counter + 1, "staffs": volunteers},
            namespace="staffs",
        )
    else:
        counter = all_volunteers["counter"]
        if counter >= len(all_volunteers["staffs"]):
            counter = 0
        staff = all_volunteers[counter]
        while staff["id"] in current_staffs:
            counter += 1
            if counter >= len(all_volunteers["staffs"]):
                counter = 0
            staff = all_volunteers[counter]
        await cache.set(
            "all_volunteers",
            {"counter": counter + 1, "staffs": all_volunteers["staffs"]},
            namespace="staffs",
        )

    # Remove all subscribed staffs for the visitor
    await delete_many(StaffSubscriptionChat, visitor_id=visitor_id)

    # Assign the chat to the staff
    if staff:
        await StaffSubscriptionChat.add_if_not_exists(
            staff_id=staff["id"], visitor_id=visitor_id
        )
    return staff


async def auto_assign_staff_to_chat(visitor_id, exclude_staff_id=None):
    # If the setting for auto-assign is off, return None
    settings = await get_settings_from_cache()
    if not settings.get("auto_assign", 1):
        return None

    all_volunteers = await cache.get("all_volunteers", namespace="staffs")
    if not all_volunteers:
        raw_volunteers = await User.query.where(
            User.role_id == ROLES.inverse["agent"], User.disabled == False
        ).gino.all()
        volunteers = [serialize_to_dict(user) for user in raw_volunteers]
        counter = 0

        # If the org has no volunteers
        if not volunteers:
            return None
        staff = volunteers[0]
        while staff["id"] == exclude_staff_id:
            counter += 1
            staff = volunteers[counter]
        await cache.set(
            "all_volunteers",
            {"counter": counter + 1, "staffs": volunteers},
            namespace="staffs",
        )
    else:
        counter = all_volunteers["counter"]
        if not all_volunteers["staffs"]:
            return None

        if counter >= len(all_volunteers["staffs"]):
            counter = 0
        staff = all_volunteers["staffs"][counter]
        while staff["id"] == exclude_staff_id:
            counter += 1
            if counter >= len(all_volunteers["staffs"]):
                counter = 0
            staff = all_volunteers["staffs"][counter]
        await cache.set(
            "all_volunteers",
            {"counter": counter + 1, "staffs": all_volunteers["staffs"]},
            namespace="staffs",
        )

    # Assign the chat to the staff
    if staff:
        await StaffSubscriptionChat.add_if_not_exists(
            staff_id=staff["id"], visitor_id=visitor_id
        )
    return staff
