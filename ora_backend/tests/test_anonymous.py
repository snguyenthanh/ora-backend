# Response's type:
# <aiohttp.client_reqrep.ClientResponse>
# Client: aiohttp
# https://docs.aiohttp.org/en/stable/client_quickstart.html#json-request

from ora_backend.models import Visitor
from ora_backend.tests import get_fake_visitor, profile_created_from_origin
from ora_backend.utils.query import get_one
from ora_backend.utils.crypto import hash_password

## GET ##


async def test_get_one_anonymous_without_token(client, visitors):
    res = await client.get("/visitors/{}".format(visitors[-3]["id"]))
    assert res.status == 401


async def test_get_one_anonymous(visitor1_client, visitors):
    res = await visitor1_client.get("/visitors/{}".format(visitors[-3]["id"]))
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    assert profile_created_from_origin(visitors[-3], body["data"])


## UPDATE ##


async def test_update_anonymous_as_self(visitors, anonymous1_client):
    new_changes = {
        "name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }

    # With id
    res = await anonymous1_client.patch(
        "/visitors/{}".format(visitors[-4]["id"]), json=new_changes
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    updated_user = await get_one(Visitor, id=visitors[-4]["id"])
    updated_user = updated_user.to_dict()

    ## Assert the new password has been updated
    assert profile_created_from_origin(
        {**body["data"], "password": hash_password(new_changes["password"])},
        updated_user,
        ignore={"updated_at"},
    )


async def test_update_anonymous_as_agent(visitors, agent1_client):
    new_changes = {
        "name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }
    # An user cannot update another user
    res = await agent1_client.patch(
        "/visitors/{}".format(visitors[-4]["id"]), json=new_changes
    )
    assert res.status == 403


async def test_update_anonymous_without_token(client, visitors):
    new_changes = {
        "name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }

    # Without token
    res = await client.patch(
        "/visitors/{}".format(visitors[-4]["id"]), json=new_changes
    )
    assert res.status == 401


async def test_update_anonymous_as_admin(visitors, admin1_client):
    new_changes = {
        "name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }
    res = await admin1_client.patch(
        "/visitors/{}".format(visitors[-4]["id"]), json=new_changes
    )
    assert res.status == 403


## REPLACE USER ##


# async def test_replace_user(client, users, token_user):
#     new_user = get_fake_user()
#     new_user.pop("id")
#
#     # Missing token
#     res = await client.put("/users/{}".format(users[0]["id"]), json=new_user)
#     assert res.status == 401
#
#     # Valid request
#     res = await client.put(
#         "/users/{}".format(users[0]["id"]),
#         json=new_user,
#         headers={"Authorization": token_user},
#     )
#     assert res.status == 200
#
#     body = await res.json()
#     assert "data" in body
#     assert isinstance(body["data"], dict)
#
#     updated_user = await get_one(User, internal_id=1)
#     updated_user = updated_user.to_dict()
#     assert profile_created_from_origin(new_user, updated_user)
#
#
# async def test_replace_user_with_invalid_args(client, users):
#     res = await client.put("/users/{}".format(users[0]["id"]), json={})
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"id": 4})
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"full_name": ""})
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"full_name": ""})
#     assert res.status == 400
#
#     res = await client.put(
#         "/users/{}".format(users[0]["id"]), json={"full_name": "Josh", "password": ""}
#     )
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"email": ""})
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"location": 2})
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"created_at": 2})
#     assert res.status == 400
#
#     res = await client.put("/users/{}".format(users[0]["id"]), json={"updated_at": 2})
#     assert res.status == 400
#
#     # Invalid or weak password
#     res = await client.put(
#         "/users/{}".format(users[0]["id"]),
#         json={"full_name": "Josh", "password": "mmmw"},
#     )
#     assert res.status == 400
#
#     res = await client.put(
#         "/users/{}".format(users[0]["id"]),
#         json={"full_name": "Josh", "password": "qweon@qweqweklasl"},
#     )
#     assert res.status == 400
#
#     # Assert no new users are created
#     all_users = await User.query.gino.all()
#     assert len(all_users) == len(users)
#     updated_user = await get_one(User, internal_id=1)
#     updated_user = updated_user.to_dict()
#     assert profile_created_from_origin(users[0], updated_user)


## DELETE ##


# async def test_delete_user(client, users, token_admin, token_mod, token_user):
#     # As admin
#     res = await client.delete("/users?id=7", headers={"Authorization": token_admin})
#     assert res.status == 200
#
#     body = await res.json()
#     assert "data" in body
#     assert body["data"] is None
#
#     all_users = await User.query.gino.all()
#     assert len(all_users) == len(users)
#     disabled_users_count = 0
#     for user in all_users:
#         if user.to_dict()["disabled"]:
#             disabled_users_count += 1
#     assert disabled_users_count == 1
#
#     # Without token
#     res = await client.delete("/users?id=7")
#     assert res.status == 401
#
#     # As mod
#     res = await client.delete("/users?id=7", headers={"Authorization": token_mod})
#     assert res.status == 401
#
#     # As user
#     res = await client.delete("/users?id=7", headers={"Authorization": token_user})
#     assert res.status == 401
#
#     # No new users are "deleted"
#     all_users = await User.query.gino.all()
#     assert len(all_users) == len(users)
#     disabled_users_count = 0
#     for user in all_users:
#         if user.to_dict()["disabled"]:
#             disabled_users_count += 1
#     assert disabled_users_count == 1


# async def test_delete_user_self(client, users, token_user):
#     # User can only "delete" himself/herself
#     res = await client.delete("/users?id=23", headers={"Authorization": token_user})
#     assert res.status == 200
#
#     # No new users are "deleted"
#     all_users = await User.query.gino.all()
#     assert len(all_users) == len(users)
#
#     deleted_user = await User.get(id=23)
#     assert deleted_user["disabled"]
#
#     # Ensure only 1 user is "deleted"
#     disabled_users_count = 0
#     for user in all_users:
#         if user.to_dict()["disabled"]:
#             disabled_users_count += 1
#     assert disabled_users_count == 1
