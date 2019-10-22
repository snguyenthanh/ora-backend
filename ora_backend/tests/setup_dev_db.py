import sys
from os.path import abspath, dirname

root_dir = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(root_dir)

from ora_backend import db
from ora_backend.models import User, Organisation
from ora_backend.tests import get_fake_organisation
from ora_backend.tests.fixtures import users as _users, organisations as _orgs
from ora_backend.utils.crypto import hash_password


async def setup_db():
    "Re-setup the DB"
    # Create a test org
    org_data = _orgs[0]
    org = await Organisation(**org_data).create()

    # Register all users under the same org
    for user in _users:
        user["password"] = hash_password(user["password"])
        await User(**user, organisation_id=org.id).create()


if __name__ == "__main__":
    import asyncio
    import uvloop

    from ora_backend.config.db import get_db_url

    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.set_bind(get_db_url()))
    loop.run_until_complete(db.gino.create_all())
    loop.run_until_complete(setup_db())
