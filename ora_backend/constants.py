from bidict import bidict

# User roles (Staff)
# 1. Admin
# 2. Supervisor
# 3. Agent
ROLES = bidict({1: "admin", 2: "supervisor", 3: "agent"})

DEFAULT_SEVERITY_LEVEL_OF_CHAT = 0

# SOCKET.IO
UNCLAIMED_CHATS_PREFIX = "cache_unclaimed_chats_"
ONLINE_USERS_PREFIX = "cache_online_users_"
ONLINE_VISITORS_PREFIX = "cache_online_visitors_"
MONITOR_ROOM_PREFIX = "cache_monitor_room_"

# LOAD BALANCER
SERVER_IDS = [
    "9cc8528fc3",  # Port: 8080
    "116e7af4ef",  # Port: 8081
    "80dd3b3290",  # Port: 8082
]
