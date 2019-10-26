from ora_backend.config import CORS_ORIGINS


async def test_check_cors_is_working(admin1_client):
    res = await admin1_client.get("/users")
    assert res.status == 200
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] == CORS_ORIGINS
