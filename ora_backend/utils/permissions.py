from ora_backend.models import RolePermission


async def role_is_authorized(role_id: str, action_name: str) -> bool:
    permission = await RolePermission.get(name=action_name, role_id=role_id)
    if permission:
        return True
    return False
