from ora_backend.constants import ROLES
from ora_backend.models import User, NotificationStaff


async def send_notifications_to_all_high_ups(content: dict):
    all_high_ups_users = await User.query.get(User.role_id < ROLES.inverse["agent"])
    notifications = [
        {"staff_id": user["id"], "content": content} for user in all_high_ups_users
    ]
    await NotificationStaff.bulk_upsert(notifications)
