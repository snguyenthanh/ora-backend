from bidict import bidict

# User roles (Staff)
# 1. Admin
# 2. Supervisor
# 3. Agent
ROLES = bidict({1: "admin", 2: "supervisor", 3: "agent"})

UNCLAIMED_CHATS_PREFIX = "cache_unclaimed_chats_"
