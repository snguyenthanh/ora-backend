from ora_backend.tests import profile_created_from_origin


async def test_login_anonymous(client):
    """Anonymous login means creating a new accoun"""
    res = await client.post("/anonymous/login", json={"name": "George"})
    assert res.status == 200

    body = await res.json()
    assert isinstance(body, dict)
    assert "access_token" in body and "refresh_token" not in body
    assert "user" in body
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies
    assert profile_created_from_origin(
        body["user"],
        {"name": "George", "is_anonymous": True, "email": None, "disabled": False},
        ignore={"id"},
    )


async def test_login_visitor(client, visitors):
    for user in visitors[:-4] + visitors[-2:]:
        res = await client.post(
            "/visitor/login",
            json={"email": user["email"], "password": user["password"]},
        )
        assert res.status == 200

        body = await res.json()
        assert isinstance(body, dict)
        assert "access_token" in body and "refresh_token" not in body
        assert "user" in body
        assert "access_token" in res.cookies
        assert "refresh_token" in res.cookies
        assert profile_created_from_origin(
            body["user"], user, ignore={"is_anonymous", "disabled"}
        )
        assert not body["user"]["is_anonymous"]
        assert not body["user"]["disabled"]

    # Login with wrong password
    user = visitors[-1]
    res = await client.post(
        "/visitor/login", json={"email": user["email"], "password": "qkwlemk123l1kn"}
    )
    assert res.status == 401

    # Login with weak password
    user = visitors[-1]
    res = await client.post(
        "/visitor/login", json={"email": user["email"], "password": "0"}
    )
    assert res.status == 401

    # Login with missing password
    user = visitors[-1]
    res = await client.post("/visitor/login", json={"email": user["email"]})
    assert res.status == 400

    # Login with missing email
    user = visitors[-1]
    res = await client.post("/visitor/login", json={"password": user["password"]})
    assert res.status == 400


async def test_login_user(client, users):
    for user in users[-4:-1]:
        res = await client.post(
            "/login", json={"email": user["email"], "password": user["password"]}
        )
        assert res.status == 200

        body = await res.json()
        assert isinstance(body, dict)
        assert "access_token" in body and "refresh_token" not in body
        assert "user" in body
        assert "access_token" in res.cookies
        assert "refresh_token" in res.cookies
        assert profile_created_from_origin(user, body["user"])

    # Login with wrong password
    user = users[-1]
    res = await client.post(
        "/login", json={"email": user["email"], "password": "qkwlemk123l1kn"}
    )
    assert res.status == 401

    # Login with weak password
    user = users[-1]
    res = await client.post("/login", json={"email": user["email"], "password": "0"})
    assert res.status == 401

    # Login with missing password
    user = users[-1]
    res = await client.post("/login", json={"email": user["email"]})
    assert res.status == 400

    # Login with missing email
    user = users[-1]
    res = await client.post("/login", json={"password": user["password"]})
    assert res.status == 400


async def test_refresh_token_anonymous(anonymous1_client):
    res = await anonymous1_client.post("/refresh")
    assert res.status == 200

    body = await res.json()
    assert isinstance(body, dict)
    assert "access_token" in body
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies


async def test_refresh_token_visitor(visitor1_client):
    res = await visitor1_client.post("/refresh")
    assert res.status == 200

    body = await res.json()
    assert isinstance(body, dict)
    assert "access_token" in body
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies


async def test_refresh_token_user(agent1_client):
    # Get a new access token
    res = await agent1_client.post("/refresh")
    assert res.status == 200

    body = await res.json()
    assert isinstance(body, dict)
    assert "access_token" in body
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies
    # new_access_token = body["access_token"]

    # # Try to create a quiz using the created refresh_token
    # fake_quiz = get_fake_quiz()
    # fake_quiz.pop("creator_id")
    # new_quiz = {**fake_quiz, "questions": get_fake_quiz_questions(has_id=False)}
    # new_quiz.pop("id", None)
    #
    # # Create a quiz with valid args
    # res = await client.post(
    #     "/quizzes", json=new_quiz, headers={"Authorization": new_access_token}
    # )
    # assert res.status == 200
