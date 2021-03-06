import sys
from os.path import abspath, dirname

root_dir = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(root_dir)

from ora_backend.constants import ROLES, DEFAULT_GLOBAL_SETTINGS
from ora_backend.models import generate_uuid
from ora_backend.tests import (
    get_fake_user,
    get_fake_organisation,
    get_fake_visitor,
    number_of_users,
    number_of_visitors,
)

organisations = [get_fake_organisation()]
user_roles = [{"id": role, "name": value} for role, value in ROLES.items()]
settings = [{"key": "max_staffs_in_chat", "value": 5}]
settings = [
    {"key": key, "value": value} for key, value in DEFAULT_GLOBAL_SETTINGS.items()
]

visitors = [get_fake_visitor() for _ in range(number_of_visitors)]
visitors += [
    {"id": generate_uuid(), "name": "Anonymous 1", "is_anonymous": True},
    {"id": generate_uuid(), "name": "Anonymous 2", "is_anonymous": True},
    {
        "id": generate_uuid(),
        "name": "Visitor 1",
        "email": "visitor1@gmail.com",
        "password": "cs3216final",
    },
    {
        "id": generate_uuid(),
        "name": "Visitor 2",
        "email": "visitor2@gmail.com",
        "password": "cs3216final",
    },
]
users = [get_fake_user() for _ in range(number_of_users)]
users += [
    {
        "id": generate_uuid(),
        "full_name": "Agent 1",
        "email": "agent1@gmail.com",
        "password": "cs3216final",
        "disabled": False,
    },
    {
        "id": generate_uuid(),
        "full_name": "Agent 2",
        "email": "agent2@gmail.com",
        "password": "cs3216final",
        "disabled": False,
    },
    {
        "id": generate_uuid(),
        "full_name": "Supervisor 1",
        "email": "supervisor1@gmail.com",
        "password": "cs3216final",
        "role_id": 2,
        "disabled": False,
    },
    {
        "id": generate_uuid(),
        "full_name": "Supervisor 2",
        "email": "supervisor2@gmail.com",
        "password": "cs3216final",
        "role_id": 2,
        "disabled": False,
    },
    {
        "id": generate_uuid(),
        "full_name": "Admin 1",
        "email": "admin1@gmail.com",
        "password": "cs3216final",
        "role_id": 1,
        "disabled": False,
    },
    {
        "id": generate_uuid(),
        "full_name": "Admin 2",
        "email": "admin2@gmail.com",
        "password": "cs3216final",
        "role_id": 1,
        "disabled": False,
    },
]
