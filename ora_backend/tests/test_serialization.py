from ora_backend.tests import get_fake_user


async def test_create_internal_id_users(client, token_supervisor_1):
    """Ensure that `internal_id` cannot be created"""
    new_user = get_fake_user()
    new_user.pop("id")

    res = await client.post(
        "/users",
        json={**new_user, "internal_id": 3},
        headers={"Authorization": token_supervisor_1},
    )
    assert res.status == 400


async def test_update_internal_id_users(client, users, token_supervisor_1):
    """Ensure that `internal_id` cannot be updated"""
    res = await client.patch(
        "/users/{}".format(users[0]["id"]),
        json={"internal_id": 22},
        headers={"Authorization": token_supervisor_1},
    )
    assert res.status == 400
