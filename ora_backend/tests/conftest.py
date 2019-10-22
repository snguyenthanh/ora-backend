import asyncio
import pytest
import uvloop
from sanic_jwt_extended import create_access_token

from ora_backend import app as _app, db
from ora_backend.tests.setup_dev_db import setup_db
from ora_backend.tests import get_access_token_for_user
from ora_backend.tests.fixtures import users as _users, organisations as _orgs
from ora_backend.config.db import get_db_url


## Keep this here, in case we find a way to implement rollback
def pytest_configure(config):
    # Create a new event loop
    # as the pytest's loop is not created
    loop = uvloop.new_event_loop()

    loop.run_until_complete(db.set_bind(get_db_url()))
    loop.run_until_complete(db.gino.create_all())


@pytest.fixture(autouse=True)
async def reset_db():
    await db.set_bind(get_db_url())

    # Clear the DB
    await db.status(db.text("""TRUNCATE "organisation" RESTART IDENTITY CASCADE;"""))
    await db.status(db.text("""TRUNCATE "visitor" RESTART IDENTITY CASCADE;"""))

    # Re-setup the db
    await setup_db()


@pytest.fixture
def app():
    yield _app


@pytest.fixture
def client(loop, app, sanic_client):
    return loop.run_until_complete(sanic_client(app))


@pytest.fixture
def users():
    return _users


@pytest.fixture
async def token_admin_2(app):
    return await get_access_token_for_user(
        {**_users[-1], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
async def token_admin_1(app):
    return await get_access_token_for_user(
        {**_users[-2], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
async def token_supervisor_2(app):
    return await get_access_token_for_user(
        {**_users[-3], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
async def token_supervisor_1(app):
    return await get_access_token_for_user(
        {**_users[-4], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
async def token_agent_2(app):
    return await get_access_token_for_user(
        {**_users[-5], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
async def token_agent_1(app):
    return await get_access_token_for_user(
        {**_users[-6], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
    )
