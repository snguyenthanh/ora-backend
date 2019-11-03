from copy import deepcopy

from ora_backend.models import Visitor, Chat, ChatMessage, BookmarkVisitor
from ora_backend.tests import (
    get_fake_visitor,
    profile_created_from_origin,
    fake,
    get_next_page_link,
)
from ora_backend.utils.query import get_one
from ora_backend.utils.crypto import hash_password

## GET ##


async def test_get_visitor_bookmark_without_token(client, visitors):
    res = await client.get("/visitors/{}/bookmark".format(visitors[2]["id"]))
    assert res.status == 401


async def test_get_visitor_bookmark(supervisor1_client, visitors, users):
    res = await supervisor1_client.get(
        "/visitors/{}/bookmark".format(visitors[2]["id"])
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    assert profile_created_from_origin(
        {
            "staff_id": users[-4]["id"],
            "visitor_id": visitors[2]["id"],
            "is_bookmarked": False,
        },
        body["data"],
    )


## UPDATE ##


async def test_update_visitor_bookmark(supervisor1_client, visitors, users):
    visitor_id = visitors[4]["id"]
    res = await supervisor1_client.patch("/visitors/{}/bookmark".format(visitor_id))
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)
    assert profile_created_from_origin(
        {"staff_id": users[-4]["id"], "visitor_id": visitor_id, "is_bookmarked": False},
        body["data"],
    )


async def test_update_visitor_bookmark_existing(supervisor1_client, visitors, users):
    visitor_id = visitors[4]["id"]

    # A bookmark will be auto created on GET/UPDATE
    res = await supervisor1_client.get(
        "/visitors/{}/bookmark".format(visitors[2]["id"])
    )
    assert res.status == 200

    res = await supervisor1_client.patch(
        "/visitors/{}/bookmark".format(visitor_id), json={"is_bookmarked": True}
    )
    assert res.status == 200

    body = await res.json()
    assert "data" in body
    assert isinstance(body["data"], dict)

    assert profile_created_from_origin(
        {"staff_id": users[-4]["id"], "visitor_id": visitor_id, "is_bookmarked": True},
        body["data"],
    )


async def test_get_visitor_bookmark_of_staff(supervisor1_client, users):
    # Create some visitors
    visitors = []
    for _ in range(32):
        new_visitor = get_fake_visitor()
        new_visitor.pop("id")

        res = await supervisor1_client.post("/visitors", json=new_visitor)
        assert res.status == 200
        body = await res.json()
        visitors.append(body["data"])

    # Bookmark some visitors
    for visitor in visitors:
        res = await supervisor1_client.patch(
            "/visitors/{}/bookmark".format(visitor["id"]), json={"is_bookmarked": True}
        )
        assert res.status == 200

    visitors = visitors[::-1]

    # Get the bookmarked visitors
    res = await supervisor1_client.get("/visitors/bookmarked")
    body = await res.json()
    assert res.status == 200
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "links" in body and "next" in body["links"]
    assert len(body["data"]) == 15
    for expected, actual in zip(visitors[:15], body["data"]):
        assert profile_created_from_origin(expected, actual)

    # Next page
    next_page_link = get_next_page_link(body)
    res = await supervisor1_client.get(next_page_link)
    body = await res.json()
    assert res.status == 200
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "links" in body and "next" in body["links"]
    assert len(body["data"]) == 15
    for expected, actual in zip(visitors[15:30], body["data"]):
        assert profile_created_from_origin(expected, actual)

    # Last page
    next_page_link = get_next_page_link(body)
    res = await supervisor1_client.get(next_page_link)
    body = await res.json()
    assert res.status == 200
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "links" in body and "next" in body["links"]
    assert len(body["data"]) == 2

    for expected, actual in zip(visitors[30:], body["data"]):
        assert profile_created_from_origin(expected, actual)
