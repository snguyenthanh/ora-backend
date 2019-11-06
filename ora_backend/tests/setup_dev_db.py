import sys
from os.path import abspath, dirname
from copy import deepcopy
from os import environ
import ssl

root_dir = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(root_dir)

from ora_backend import db
from ora_backend.models import User, Organisation, Visitor
from ora_backend.tests import get_fake_organisation
from ora_backend.tests.fixtures import (
    users as _users,
    organisations as _orgs,
    visitors as _visitors,
)
from ora_backend.utils.crypto import hash_password


async def setup_db():
    "Re-setup the DB"
    # Create a test org
    org_data = _orgs[0]
    org = await Organisation(**org_data).create()

    # Register all users under the same org
    for user in _users:
        _user = deepcopy(user)
        _user["password"] = hash_password(_user["password"])
        await User(**_user, organisation_id=org.id).create()

    # Register the visitors
    for visitor in _visitors:
        _visitor = deepcopy(visitor)

        # Anonymous users don't have passwords
        if "password" in _visitor:
            _visitor["password"] = hash_password(_visitor["password"])
        await Visitor(**_visitor).create()


if __name__ == "__main__":
    import asyncio
    import uvloop

    from ora_backend.config.db import get_db_url

    ssl_ctx = None
    DB_CERT = environ.get("DB_CERT")
    if DB_CERT:
        ssl_ctx = ssl.create_default_context(cafile=DB_CERT)

    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)
    if ssl_ctx:
        loop.run_until_complete(db.set_bind(get_db_url(), ssl=ssl_ctx))
    else:
        loop.run_until_complete(db.set_bind(get_db_url()))
    loop.run_until_complete(db.gino.create_all())
    loop.run_until_complete(setup_db())
