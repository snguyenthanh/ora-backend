# Response's type:
# <aiohttp.client_reqrep.ClientResponse>
# Client: aiohttp
# https://docs.aiohttp.org/en/stable/client_quickstart.html#json-request

from ora_backend.constants import ROLES
from ora_backend.models import User
from ora_backend.tests import get_fake_user, profile_created_from_origin
from ora_backend.utils.query import get_one
from ora_backend.utils.crypto import hash_password

## GET ##


async def test_get_one_user_without_token(client, users):
    res = await client.get("/users/{}".format(users[2]["id"]))
    assert res.status == 401

async def test_disabled_staff_do_things(disabled_agent_client, users):
    res = await disabled_agent_client.get("/users/{}".format(users[2]["id"]))
    assert res.status == 401

async def test_get_one_user(agent1_client, users):
    res = await agent1_client.get("/users/{}".format(users[0]["id"]))
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    assert profile_created_from_origin(users[0], body["data"])

    # User doesnt exist
    res = await agent1_client.get("/users/{}".format("9" * 32))
    assert res.status == 404

    res = await agent1_client.get("/users/true")
    assert res.status == 404


async def test_get_all_users(supervisor1_client, users):
    res = await supervisor1_client.get("/users")
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 11  # Default offset for User is 11
    assert all(
        profile_created_from_origin(origin, created)
        for origin, created in zip(users, body["data"])
    )

    # GET request will have its body ignored.
    res = await supervisor1_client.get("/users", json={"id": 3})
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 11  # Default offset for User is 11

    # Get one user by id
    res = await supervisor1_client.get("/users?id={}".format(users[2]["id"]))
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1
    assert profile_created_from_origin(users[2], body["data"][0])

    ## LIMIT ##
    # No users
    res = await supervisor1_client.get("/users?limit=0")
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert not body["data"]

    # 10 users
    res = await supervisor1_client.get("/users?limit=10")
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 10
    assert all(
        profile_created_from_origin(origin, created)
        for origin, created in zip(users[:10], body["data"])
    )

    # Get the next 10 users
    next_page_link = body["links"]["next"]
    # Strip the host, as it is a testing host
    next_page_link = "/" + "/".join(next_page_link.split("/")[3:])
    res = await supervisor1_client.get(next_page_link)
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1
    assert all(
        profile_created_from_origin(origin, created)
        for origin, created in zip(users[10:11], body["data"])
    )

    # -1 users
    res = await supervisor1_client.get("/users?limit=-1")
    assert res.status == 400


async def test_get_all_agents(users, supervisor1_client):
    res = await supervisor1_client.get(
        "/users?role_id={}".format(ROLES.inverse["agent"])
    )
    assert res.status == 200
    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert all(user["role_id"] == ROLES.inverse["agent"] for user in body["data"])

    for expected, actual in zip(users[-6:-4], body["data"][-2:]):
        profile_created_from_origin(expected, actual)


async def test_get_users_with_after_id(users, supervisor1_client):
    # Use after_id in query parameter.
    res = await supervisor1_client.get("/users?after_id={}".format(users[2]["id"]))
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 8

    # Check if all profiles match from id 4 to 19
    assert all(
        profile_created_from_origin(origin, created)
        for origin, created in zip(users[3:20], body["data"])
    )

    # Invalid after_id
    res = await supervisor1_client.get("/users?after_id=2")
    assert res.status == 404

    res = await supervisor1_client.get("/users?after_id=")
    assert res.status == 400


## CREATE ##


async def test_create_user_without_token(client):
    new_user = get_fake_user()
    new_user.pop("id")

    # Missing token
    res = await client.post("/users", json=new_user)
    assert res.status == 401


async def test_create_user_as_agent(agent1_client):
    # An agent cannot create another agent
    new_user = get_fake_user()
    new_user.pop("id")
    res = await agent1_client.post("/users", json=new_user)
    assert res.status == 403


async def test_create_user_as_admin(users, admin1_client):
    new_user = get_fake_user()
    new_user.pop("id")

    # Valid
    res = await admin1_client.post("/users", json=new_user)
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)

    all_users = await User.query.gino.all()
    assert len(all_users) == len(users) + 1
    assert profile_created_from_origin(new_user, all_users[-1].to_dict())

    # Valid
    new_user = get_fake_user()
    new_user.pop("id")
    res = await admin1_client.post("/users", json=new_user)
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)

    all_users = await User.query.gino.all()
    assert len(all_users) == len(users) + 2
    assert profile_created_from_origin(new_user, all_users[-1].to_dict())

    # Create an existing user
    res = await admin1_client.post("/users", json=new_user)
    assert res.status == 400


async def test_create_user_as_supervisor(users, supervisor1_client):
    new_user = get_fake_user()
    new_user.pop("id")

    # Valid
    res = await supervisor1_client.post("/users", json=new_user)
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)

    all_users = await User.query.gino.all()
    assert len(all_users) == len(users) + 1
    assert profile_created_from_origin(new_user, all_users[-1].to_dict())

    # Valid
    new_user = get_fake_user()
    new_user.pop("id")
    res = await supervisor1_client.post("/users", json=new_user)
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)

    all_users = await User.query.gino.all()
    assert len(all_users) == len(users) + 2
    assert profile_created_from_origin(new_user, all_users[-1].to_dict())

    # Create an existing user
    res = await supervisor1_client.post("/users", json=new_user)
    assert res.status == 400


async def test_create_user_with_invalid_args(users, supervisor1_client):
    res = await supervisor1_client.post("/users", json={})
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"id": 4})
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"full_name": ""})
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"full_name": ""})
    assert res.status == 400

    res = await supervisor1_client.post(
        "/users", json={"full_name": "Josh", "password": ""}
    )
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"email": ""})
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"location": 2})
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"created_at": 2})
    assert res.status == 400

    res = await supervisor1_client.post("/users", json={"updated_at": 2})
    assert res.status == 400

    # Invalid or weak password
    res = await supervisor1_client.post(
        "/users", json={"full_name": "Josh", "password": "mmmw"}
    )
    assert res.status == 400

    res = await supervisor1_client.post(
        "/users", json={"full_name": "Josh", "password": "qweon@qweqweklasl"}
    )
    assert res.status == 400

    # Assert no new users are created
    all_users = await User.query.gino.all()
    assert len(all_users) == len(users)


## UPDATE ##


async def test_update_user_as_self(users, agent1_client):
    new_changes = {
        "full_name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }

    # With id
    res = await agent1_client.patch(
        "/users/{}".format(users[-6]["id"]), json=new_changes
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    updated_user = await get_one(User, id=users[-6]["id"])
    updated_user = updated_user.to_dict()

    ## Assert the new password has been updated
    assert profile_created_from_origin(
        {**body["data"], "password": hash_password(new_changes["password"])},
        updated_user,
        ignore={"updated_at"},
    )


async def test_update_user_as_agent(users, agent1_client):
    new_changes = {
        "full_name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }
    # An user cannot update another user
    res = await agent1_client.patch(
        "/users/{}".format(users[3]["id"]), json=new_changes
    )
    assert res.status == 403


async def test_update_user_without_token(client, users):
    new_changes = {
        "full_name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }

    # Without token
    res = await client.patch("/users/{}".format(users[0]["id"]), json=new_changes)
    assert res.status == 401


async def test_update_one_user_as_supervisor(users, supervisor1_client):
    new_changes = {
        "full_name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }

    # With id
    res = await supervisor1_client.patch(
        "/users/{}".format(users[0]["id"]), json=new_changes
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    updated_user = await get_one(User, internal_id=1)
    updated_user = updated_user.to_dict()

    ## Assert the new password has been updated
    assert profile_created_from_origin(
        {**body["data"], "password": hash_password(new_changes["password"])},
        updated_user,
    )

    # User doesnt exist
    res = await supervisor1_client.patch("/users/{}".format("9" * 32), json=new_changes)
    assert res.status == 404

    # Update to a weak password
    new_changes = {"password": "mmmk"}
    res = await supervisor1_client.patch(
        "/users/{}".format(users[1]["id"]), json=new_changes
    )
    assert res.status == 400


async def test_update_user_as_admin(users, admin1_client):
    new_changes = {
        "full_name": "this name surely doesnt exist",
        "password": "strong_password_123",
    }
    res = await admin1_client.patch(
        "/users/{}".format(users[5]["id"]), json=new_changes
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    updated_user = await get_one(User, internal_id=6)
    updated_user = updated_user.to_dict()

    ## Assert the new password has been updated
    assert profile_created_from_origin(
        {**body["data"], "password": hash_password(new_changes["password"])},
        updated_user,
    )

    # Admin can update supervisor
    res = await admin1_client.patch(
        "/users/{}".format(users[-3]["id"]), json=new_changes
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    updated_user = await get_one(User, id=users[-3]["id"])
    updated_user = updated_user.to_dict()

    ## Assert the new password has been updated
    assert profile_created_from_origin(
        {**body["data"], "password": hash_password(new_changes["password"])},
        updated_user,
    )


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
