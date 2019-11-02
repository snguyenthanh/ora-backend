from time import time

from uuid import uuid4
from sanic.exceptions import InvalidUsage, NotFound
from gino.dialects.asyncpg import ARRAY, JSON

from ora_backend import db
from ora_backend.constants import ROLES as _ROLES
from ora_backend.exceptions import LoginFailureError
from ora_backend.utils.query import (
    get_one,
    get_one_latest,
    get_many,
    create_one,
    update_one,
    delete_many,
    execute,
    get_messages,
)
from ora_backend.utils.crypto import hash_password, validate_password_strength
from ora_backend.utils.exceptions import raise_not_found_exception
from ora_backend.utils.serialization import serialize_to_dict


ROLES = set(_ROLES.values())


def generate_uuid():
    return uuid4().hex


def unix_time():
    """Return the current unix timestamp."""
    return int(time())


class BaseModel(db.Model):
    permissions = {
        "GET": ROLES,
        "POST": ROLES,
        "PUT": ROLES,
        "PATCH": ROLES,
        "DELETE": ROLES,
    }

    @classmethod
    async def get(
        cls,
        many=False,
        after_id=None,
        limit=15,
        fields=None,
        in_column=None,
        in_values=None,
        allow_readonly=False,
        order_by="internal_id",
        **kwargs,
    ):
        """
        Retrieve the row(s) of a model, using Keyset Pagination (after_id).

        Kwargs:
            after_id (str):
                The returned result will start from row
                with id == after_id (exclusive).

                Ignored if many=False.
        """
        # Using an param `many` to optimize Select queries for single row
        if many:
            data = await get_many(
                cls,
                after_id=after_id,
                limit=limit,
                in_column=in_column,
                in_values=in_values,
                order_by=order_by,
                **kwargs,
            )
        else:
            data = await get_one(cls, **kwargs)

        serialized_data = serialize_to_dict(
            data, fields=fields, allow_readonly=allow_readonly
        )

        # Raise NotFound if no single resource is found
        # Ignore if many=True, as returning an empty List is expected
        if not many and not serialized_data:
            raise_not_found_exception(cls, **kwargs)

        return serialized_data

    @classmethod
    async def add(cls, **kwargs):
        data = await create_one(cls, **kwargs)
        return serialize_to_dict(data)

    @classmethod
    async def modify(cls, get_kwargs, update_kwargs):
        model_id = get_kwargs.get("id")
        if not model_id:
            raise InvalidUsage("Missing field 'id' in query parameter")

        payload = await get_one(cls, id=model_id)
        if not payload:
            raise_not_found_exception(cls, id=model_id)

        data = await update_one(payload, **update_kwargs)
        return serialize_to_dict(data)

    @classmethod
    async def remove(cls, **kwargs):
        model_id = kwargs.get("id")
        if not model_id:
            raise InvalidUsage("Missing field 'id' in query parameter")

        model = await get_one(cls, id=model_id)
        if not model:
            raise_not_found_exception(cls, id=model_id)

        await model.delete()


class Organisation(BaseModel):
    __tablename__ = "organisation"
    permissions = {"GET": ROLES, "POST": {}, "PUT": {}, "PATCH": {}, "DELETE": {}}

    id = db.Column(
        db.String(length=32), nullable=False, unique=True, default=generate_uuid
    )
    internal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    disabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.BigInteger, nullable=False, default=unix_time)
    updated_at = db.Column(db.BigInteger, onupdate=unix_time)

    # Index
    _idx_org_id = db.Index("idx_org_id", "id")
    _idx_org_disabled = db.Index("idx_org_disabled", "disabled")


class BaseUser(BaseModel):
    @classmethod
    async def add(cls, password=None, **kwargs):
        # Follow guidelines from OWASP
        # https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
        if password:
            validate_password_strength(password)
            password = hash_password(password)

        return await super(BaseUser, cls).add(password=password, **kwargs)

    @classmethod
    async def modify(cls, get_kwargs, update_kwargs):
        if "password" in update_kwargs:
            password = update_kwargs["password"]
            validate_password_strength(password)
            update_kwargs["password"] = hash_password(password)

        return await super(BaseUser, cls).modify(get_kwargs, update_kwargs)

    @classmethod
    async def remove(cls, **kwargs):
        """For User, only disabled it, without completely delete it."""
        if "id" not in kwargs:
            raise InvalidUsage("Missing field 'id' in query parameter")

        await super(BaseUser, cls).modify(kwargs, {"disabled": True})

    @classmethod
    async def login(cls, email=None, password=None, *, is_anonymous=False, **kwargs):
        user = None
        if not is_anonymous:
            if not email:
                raise InvalidUsage("Missing field 'email' in request's body.")
            if not password:
                raise InvalidUsage("Missing field 'password' in request's body.")

            password = hash_password(password)
            try:
                user = await cls.get(email=email, password=password, **kwargs)
            except NotFound:
                pass

            if not user:
                raise LoginFailureError()
        else:  # Anonymous login
            kwargs["is_anonymous"] = True
            user = await cls.add(**kwargs)

        # Only store minimum info for user
        fields = {
            "id",
            "full_name",
            "display_name",
            "name",
            "email",
            "role_id",
            "organisation_id",
            "is_anonymous",
            "disabled",
        }
        for key in list(user.keys()):
            if key not in fields:
                user.pop(key, None)

        return user


class Visitor(BaseUser):
    __tablename__ = "visitor"

    id = db.Column(
        db.String(length=32), nullable=False, unique=True, default=generate_uuid
    )
    internal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=True)
    password = db.Column(db.String, nullable=True)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    disabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.BigInteger, nullable=False, default=unix_time)
    updated_at = db.Column(db.BigInteger, onupdate=unix_time)

    # Index
    _idx_visitor_id = db.Index("idx_visitor_id", "id")
    _idx_visitor_email = db.Index("idx_visitor_email", "email")


class User(BaseUser):
    __tablename__ = "user"
    permissions = {
        "GET": ROLES,
        "POST": {"supervisor", "admin"},
        "PUT": {"supervisor", "admin"},
        "PATCH": {"supervisor", "admin"},
        "DELETE": {"supervisor", "admin"},
    }

    id = db.Column(
        db.String(length=32), nullable=False, unique=True, default=generate_uuid
    )
    internal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String, nullable=False)
    display_name = db.Column(db.String)
    role_id = db.Column(db.SmallInteger, nullable=False, default=3)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    disabled = db.Column(db.Boolean, nullable=False, default=False)
    organisation_id = db.Column(
        db.String(length=32), db.ForeignKey("organisation.id"), nullable=False
    )
    created_at = db.Column(db.BigInteger, nullable=False, default=unix_time)
    updated_at = db.Column(db.BigInteger, onupdate=unix_time)

    # Index
    _idx_user_id = db.Index("idx_user_id", "id")
    _idx_user_email = db.Index("idx_user_email", "email")
    _idx_user_role_id = db.Index("idx_user_role_id", "role_id")
    _idx_user_organisation_id = db.Index("_idx_user_organisation_id", "organisation_id")


class ChatMessage(BaseModel):
    __tablename__ = "chat_message"

    id = db.Column(db.String(length=32), primary_key=True, default=generate_uuid)
    sequence_num = db.Column(db.BigInteger, nullable=False, default=0)
    chat_id = db.Column(db.String(length=32), nullable=False)
    type_id = db.Column(db.SmallInteger, nullable=False, default=1)
    sender = db.Column(db.String(length=32), nullable=True)
    content = db.Column(JSON(), nullable=False, server_default="{}")
    created_at = db.Column(db.BigInteger, nullable=False, default=unix_time)
    updated_at = db.Column(db.BigInteger, onupdate=unix_time)

    # Index
    _idx_chat_msg_chat_id = db.Index("idx_chat_msg_chat_id", "chat_id")
    _idx_chat_msg_sender = db.Index("idx_chat_msg_sender", "sender")

    @classmethod
    async def get(cls, *, chat_id, **kwargs):
        messages = await get_messages(cls, User, chat_id=chat_id, **kwargs)
        # serialized_data = serialize_to_dict(messages)
        return messages


class Chat(BaseModel):
    __tablename__ = "chat"

    id = db.Column(
        db.String(length=32), nullable=False, unique=True, default=generate_uuid
    )
    internal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    visitor_id = db.Column(db.String(length=32), nullable=False)
    tags = db.Column(ARRAY(JSON()), nullable=False, server_default="{}")
    severity_level = db.Column(db.SmallInteger, nullable=False, default=0)
    created_at = db.Column(db.BigInteger, nullable=False, default=unix_time)
    updated_at = db.Column(db.BigInteger, onupdate=unix_time)

    # Index
    _idx_chat_id = db.Index("idx_chat_id", "id")
    _idx_chat_visitor = db.Index("idx_chat_visitor", "visitor_id")
    _idx_chat_severity_level = db.Index("idx_chat_severity_level", "severity_level")

    @classmethod
    async def get_or_create(cls, **kwargs):
        created_attempt = await get_one(cls, **kwargs)

        # Update the number of attempts in Quiz, if no previous attempts of the user are found
        if not created_attempt:
            data = await create_one(cls, **kwargs)
            return serialize_to_dict(data)

        return serialize_to_dict(created_attempt)


class ChatMessageSeen(BaseModel):
    __tablename__ = "chat_message_seen"

    id = db.Column(
        db.String(length=32), nullable=False, unique=True, default=generate_uuid
    )
    internal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    staff_id = db.Column(db.String(length=32), nullable=False)
    chat_id = db.Column(db.String(length=32), nullable=False)
    last_seen_msg_id = db.Column(db.String(length=32), nullable=True)
    created_at = db.Column(db.BigInteger, nullable=False, default=unix_time)
    updated_at = db.Column(db.BigInteger, onupdate=unix_time)

    # Index
    _idx_chat_msg_seen_id = db.Index("idx_chat_msg_seen_id", "id")
    _idx_chat_msg_seen_staff_chat = db.Index(
        "idx_chat_msg_seen_staff_chat", "staff_id", "chat_id"
    )

    @classmethod
    async def get_or_create(cls, **kwargs):
        payload = await get_one(cls, **kwargs)
        if payload:
            return serialize_to_dict(payload)

        # Create
        data = await create_one(
            cls, staff_id=kwargs["staff_id"], chat_id=kwargs["chat_id"]
        )
        return serialize_to_dict(data)

    @classmethod
    async def update_or_create(cls, get_kwargs, update_kwargs):
        payload = await get_one(cls, **get_kwargs)

        if not payload:
            data = await create_one(
                cls,
                **update_kwargs,
                staff_id=get_kwargs["staff_id"],
                chat_id=get_kwargs["chat_id"],
            )
            return serialize_to_dict(data)
        # Update the existing one
        data = await update_one(payload, **update_kwargs)
        return serialize_to_dict(data)
