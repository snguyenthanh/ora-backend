from ora_backend import cache
from ora_backend.constants import CACHE_SETTINGS, ROLES
from ora_backend.models import User, StaffSubscriptionChat
from ora_backend.utils.serialization import serialize_to_dict


async def auto_assign_staff_to_chat(visitor_id, exclude_staff_id=None):
    # If the setting for auto-assign is off, return None
    settings = await cache.get(CACHE_SETTINGS, namespace="settings")
    if not settings.get("auto_assign", 1):
        return None

    all_volunteers = await cache.get("all_volunteers", namespace="staffs")
    if not all_volunteers:
        raw_volunteers = await User.query.where(
            User.role_id == ROLES.inverse["agent"]
        ).gino.all()
        volunteers = [serialize_to_dict(user) for user in raw_volunteers]
        counter = 0
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
        if counter >= len(all_volunteers["staffs"]):
            counter = 0
        staff = all_volunteers[counter]
        while staff["id"] == exclude_staff_id:
            counter += 1
            if counter >= len(all_volunteers["staffs"]):
                counter = 0
            staff = all_volunteers[counter]
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
