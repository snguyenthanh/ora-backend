from random import choice, choices, randint
from string import ascii_lowercase, digits

from faker import Faker
from faker.providers import python as py_provider, profile as profile_provider, lorem
from sanic_jwt_extended import create_access_token, create_refresh_token

from ora_backend.models import generate_uuid

# Set up Faker
fake = Faker()
fake.add_provider(py_provider)
fake.add_provider(profile_provider)
fake.add_provider(lorem)

fake_profile_fields = ["name", "mail"]
number_of_users = 5
number_of_visitors = 3


def get_fake_password():
    return "".join(choices(ascii_lowercase, k=10) + choices(digits, k=10))


def get_fake_user():
    profile = fake.profile(fields=fake_profile_fields)
    return {
        "id": generate_uuid(),
        "full_name": profile["name"],
        "email": profile["mail"],
        "password": get_fake_password(),
    }


def get_fake_visitor():
    profile = fake.profile(fields=fake_profile_fields)
    return {
        "id": generate_uuid(),
        "name": profile["name"],
        "email": profile["mail"],
        "password": get_fake_password(),
    }


def get_fake_organisation():
    return {"id": generate_uuid(), "name": fake.profile(fields=["company"])["company"]}


async def get_access_token_for_user(user, app=None):
    token = await create_access_token(identity=user, app=app)
    # return "Bearer " + token
    return token


async def get_refresh_token_for_user(user, app=None):
    token = await create_refresh_token(identity=user, app=app)
    # return "Bearer " + token
    return token


# Helper functions


def profile_created_from_origin(origin: dict, created: dict, ignore=None):
    ignore = ignore or set()
    ignore.update({"password", "updated_at"})
    for key, val in origin.items():
        if key in ignore:
            continue

        if val != created[key]:
            return False
    return True


def get_next_page_link(request_body: dict):
    next_page_link = request_body["links"]["next"]

    # Strip the host, as it is a testing host
    next_page_link = "/" + "/".join(next_page_link.split("/")[3:])
    return next_page_link
