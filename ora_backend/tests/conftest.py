from os import environ
import ssl

import asyncio
import pytest
import uvloop
import socketio
from sanic.websocket import WebSocketProtocol

from ora_backend import app as _app, db
from ora_backend.views.chat_socketio import app as _app_socketio
from ora_backend.tests.setup_dev_db import setup_db
from ora_backend.tests import get_access_token_for_user, get_refresh_token_for_user
from ora_backend.tests.async_client import create_async_client
from ora_backend.tests.fixtures import (
    users as _users,
    organisations as _orgs,
    visitors as _visitors,
)
from ora_backend.config.db import get_db_url
from ora_backend.utils.crypto import sign_str

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

## Keep this here, in case we find a way to implement rollback
def pytest_configure(config):
    # Create a new event loop
    # as the pytest's loop is not created
    loop = uvloop.new_event_loop()
    ssl_ctx = None
    DB_CERT = environ.get("DB_CERT")
    if DB_CERT:
        ssl_ctx = ssl.create_default_context(cafile=DB_CERT)

    if ssl_ctx:
        loop.run_until_complete(db.set_bind(get_db_url(), ssl=ssl_ctx))
    else:
        loop.run_until_complete(db.set_bind(get_db_url()))
    loop.run_until_complete(db.gino.create_all())


@pytest.fixture(autouse=True)
async def reset_db():
    await db.set_bind(get_db_url())

    # Clear the DB
    await db.status(db.text("""TRUNCATE "organisation" RESTART IDENTITY CASCADE;"""))
    await db.status(db.text("""TRUNCATE "visitor" RESTART IDENTITY CASCADE;"""))
    await db.status(db.text("""TRUNCATE "chat" RESTART IDENTITY CASCADE;"""))
    await db.status(db.text("""TRUNCATE "chat_message" RESTART IDENTITY CASCADE;"""))
    await db.status(
        db.text("""TRUNCATE "bookmark_visitor" RESTART IDENTITY CASCADE;""")
    )
    await db.status(db.text("""TRUNCATE "chat_unclaimed" RESTART IDENTITY CASCADE;"""))

    # Re-setup the db
    await setup_db()


@pytest.fixture
def app():
    yield _app


@pytest.fixture
def client(loop, app, sanic_client):
    return loop.run_until_complete(sanic_client(app))


@pytest.fixture
def sio_client_visitor(loop):
    sio = socketio.AsyncClient(logger=True, request_timeout=1, engineio_logger=True)
    yield create_async_client(sio)
    loop.run_until_complete(sio.disconnect())
    # loop.run_until_complete(sio.wait())


@pytest.fixture
def sio_client_agent1(loop):
    sio = socketio.AsyncClient(logger=True, request_timeout=1, engineio_logger=True)
    yield create_async_client(sio)
    loop.run_until_complete(sio.disconnect())
    # loop.run_until_complete(sio.wait())


@pytest.fixture
def sio_client_agent2(loop):
    sio = socketio.AsyncClient(logger=True, request_timeout=1, engineio_logger=True)
    yield create_async_client(sio)
    loop.run_until_complete(sio.disconnect())
    # loop.run_until_complete(sio.wait())


@pytest.fixture
def server(loop, test_server):
    _server = loop.run_until_complete(
        test_server(_app_socketio, protocol=WebSocketProtocol)
    )
    yield _server
    loop.run_until_complete(_server.close())


@pytest.fixture
def server_path(server):
    return "{}://{}:{}".format(server.scheme, server.host, server.port)


@pytest.fixture
def users():
    return _users


@pytest.fixture
def visitors():
    return _visitors


@pytest.fixture
async def token_admin_2(app):
    return await get_access_token_for_user(
        {**_users[-1], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
def admin2_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(
            {**_users[-1], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(
            {**_users[-1], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_admin_1(app):
    return await get_access_token_for_user(
        {**_users[-2], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
def admin1_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(
            {**_users[-2], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(
            {**_users[-2], "role_id": 1, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_supervisor_2(app):
    return await get_access_token_for_user(
        {**_users[-3], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
def supervisor2_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(
            {**_users[-3], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(
            {**_users[-3], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_supervisor_1(app):
    return await get_access_token_for_user(
        {**_users[-4], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
def supervisor1_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(
            {**_users[-4], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(
            {**_users[-4], "role_id": 2, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_agent_2(app):
    return await get_access_token_for_user(
        {**_users[-5], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
    )


@pytest.fixture
def agent2_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(
            {**_users[-5], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(
            {**_users[-5], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_agent_1(app):
    return sign_str(
        await get_access_token_for_user(
            {**_users[-6], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )


@pytest.fixture
def agent1_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(
            {**_users[-6], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(
            {**_users[-6], "role_id": 3, "organisation_id": _orgs[0]["id"]}, app=app
        )
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_visitor_2(app):
    return sign_str(await get_access_token_for_user(_visitors[-2], app=app))


@pytest.fixture
def visitor2_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(_visitors[-2], app=app)
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(_visitors[-2], app=app)
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_visitor_1(app):
    return sign_str(await get_access_token_for_user(_visitors[-1], app=app))


@pytest.fixture
def visitor1_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(_visitors[-1], app=app)
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(_visitors[-1], app=app)
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_anonymous_1(app):
    return sign_str(await get_access_token_for_user(_visitors[-4], app=app))


@pytest.fixture
def anonymous1_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(_visitors[-4], app=app)
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(_visitors[-4], app=app)
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
async def token_anonymous_2(app):
    return sign_str(await get_access_token_for_user(_visitors[-3], app=app))


@pytest.fixture
def anonymous2_client(loop, app, sanic_client):
    access_token = loop.run_until_complete(
        get_access_token_for_user(_visitors[-3], app=app)
    )
    refresh_token = loop.run_until_complete(
        get_refresh_token_for_user(_visitors[-3], app=app)
    )
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))


@pytest.fixture
def disabled_agent_client(loop, app, sanic_client):
    _user = {
        **_users[2],
        "disabled": True,
        "role_id": 2,
        "organisation_id": _orgs[0]["id"],
    }
    access_token = loop.run_until_complete(get_access_token_for_user(_user, app=app))
    refresh_token = loop.run_until_complete(get_refresh_token_for_user(_user, app=app))
    cookies = {
        "access_token": sign_str(access_token),
        "refresh_token": sign_str(refresh_token),
    }
    return loop.run_until_complete(sanic_client(app, cookies=cookies))
