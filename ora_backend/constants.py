from bidict import bidict

# User roles (Staff)
# 1. Admin
# 2. Supervisor
# 3. Agent
ROLES = bidict({1: "admin", 2: "supervisor", 3: "agent"})

DEFAULT_SEVERITY_LEVEL_OF_CHAT = 0

UNCLAIMED_CHATS_PREFIX = "cache_unclaimed_chats_"
ONLINE_USERS_PREFIX = "cache_online_users_"
ONLINE_VISITORS_PREFIX = "cache_online_visitors_"
MONITOR_ROOM_PREFIX = "cache_monitor_room_"
CACHE_SETTINGS = "cache_global_settings"
CACHE_PERMISSIONS = "cache_permissions"

# Note: 0 is off
DEFAULT_GLOBAL_SETTINGS = {
    "login_type": 2,  # 0: anonymous, 1: account, 2: both
    "allow_claiming_chat": 0,
    "max_staffs_in_chat": 5,
    "auto_reassign": 1,
    "auto_assign": 1,
    "hours_to_auto_reassign": 24,
}

# The key is the permission key
# The value is the role_ids that are allowed to perform
DEFAULT_PERMISSIONS = {
    "modify_global_settings": [1],
    "reassign_agent": [1, 2],  # For one-to-many chat
    "add_agents_to_chat": [1, 2],  # For one-to-many chat
    "see_all_chats": [1, 2],
    "join_all_chats": [1, 2],
    "change_max_staffs_in_chat": [1, 2],
}
