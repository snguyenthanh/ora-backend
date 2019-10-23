from ora_backend.tests import get_fake_user


async def test_create_internal_id_users(supervisor1_client):
    """Ensure that `internal_id` cannot be created"""
    new_user = get_fake_user()
    new_user.pop("id")

    res = await supervisor1_client.post(
        "/users",
        json={**new_user, "internal_id": 3},
    )
    assert res.status == 400


async def test_update_internal_id_users(users, supervisor1_client):
    """Ensure that `internal_id` cannot be updated"""
    res = await supervisor1_client.patch(
        "/users/{}".format(users[0]["id"]),
        json={"internal_id": 22},
    )
    assert res.status == 400
