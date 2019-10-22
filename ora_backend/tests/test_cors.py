async def test_check_cors_is_working(client, token_admin_1):
    res = await client.get("/users", headers={"Authorization": token_admin_1})
    assert res.status == 200
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] == "*"
