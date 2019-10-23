import sys
from os.path import abspath, dirname

root_dir = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(root_dir)


from ora_backend.models import generate_uuid
from ora_backend.tests import (
    get_fake_user,
    get_fake_organisation,
    get_fake_visitor,
    number_of_users,
    number_of_visitors,
)

organisations = [get_fake_organisation()]
visitors = [get_fake_visitor() for _ in range(number_of_visitors)]
users = [get_fake_user() for _ in range(number_of_users)]
users += [
    {
        "id": generate_uuid(),
        "full_name": "Agent 1",
        "email": "agent1",
        "password": "cs3216final",
    },
    {
        "id": generate_uuid(),
        "full_name": "Agent 2",
        "email": "agent2",
        "password": "cs3216final",
    },
    {
        "id": generate_uuid(),
        "full_name": "Supervisor 1",
        "email": "supervisor1",
        "password": "cs3216final",
        "role_id": 2,
    },
    {
        "id": generate_uuid(),
        "full_name": "Supervisor 2",
        "email": "supervisor2",
        "password": "cs3216final",
        "role_id": 2,
    },
    {
        "id": generate_uuid(),
        "full_name": "Admin 1",
        "email": "admin1",
        "password": "cs3216final",
        "role_id": 3,
    },
    {
        "id": generate_uuid(),
        "full_name": "Admin 2",
        "email": "admin2",
        "password": "cs3216final",
        "role_id": 3,
    },
]
