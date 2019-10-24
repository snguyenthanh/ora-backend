from pprint import pprint
from unittest import mock

from pytest import raises
from socketio.exceptions import ConnectionError

from ora_backend import cache
from ora_backend.models import Chat, ChatMessage
from ora_backend.utils.query import get_one


async def test_visitor_start_chat_without_token(sio_client_visitor, server_path):
    # SocketIO raises ConnectionError on invalid/missing token
    with raises(ConnectionError):
        await sio_client_visitor.connect(server_path)

    with raises(ConnectionError):
        await sio_client_visitor.connect(
            server_path, headers={"Authorization": "Bearer 123.112.333"}
        )


async def test_visitor_start_chat(
    sio_client_visitor,
    sio_client_agent,
    server,
    server_path,
    token_visitor_1,
    token_agent_1,
    visitors,
):
    await sio_client_visitor.connect(
        server_path, headers={"Authorization": token_visitor_1}
    )
    await sio_client_agent.connect(
        server_path, headers={"Authorization": token_agent_1}
    )

    await sio_client_visitor.disconnect()
    await sio_client_agent.disconnect()
