from typing import Tuple
from itertools import chain

from asyncpg.exceptions import UniqueViolationError
from sqlalchemy import and_, desc, func

from ora_backend import db
from ora_backend.constants import DEFAULT_SEVERITY_LEVEL_OF_CHAT
from ora_backend.exceptions import UniqueViolationError as DuplicatedError
from ora_backend.schemas import (
    CHAT_MESSAGE_READ_SCHEMA,
    USER_READ_SCHEMA,
    QUERY_PARAM_READ_SCHEMA,
    VISITOR_READ_SCHEMA,
    BOOKMARK_VISITOR_READ_SCHEMA,
    CHAT_READ_SCHEMA,
)
from ora_backend.utils.exceptions import raise_not_found_exception
from ora_backend.utils.transaction import in_transaction


# Define fields for custom selection
ignore_fields = set(QUERY_PARAM_READ_SCHEMA.keys())
chat_fields = [
    key
    for key, val in CHAT_READ_SCHEMA.items()
    if not val.get("readonly", False) and key not in ignore_fields
]
message_fields = [
    key
    for key, val in CHAT_MESSAGE_READ_SCHEMA.items()
    if not val.get("readonly", False) and key not in ignore_fields
]
user_fields = [
    key
    for key, val in USER_READ_SCHEMA.items()
    if not val.get("readonly", False) and key not in ignore_fields
]
visitor_fields = [
    key
    for key, val in VISITOR_READ_SCHEMA.items()
    if not val.get("readonly", False) and key not in ignore_fields
]
bookmark_fields = [
    key
    for key, val in BOOKMARK_VISITOR_READ_SCHEMA.items()
    if not val.get("readonly", False) and key not in ignore_fields
]


def dict_to_filter_args(model, **kwargs):
    """
    Convert a dictionary to Gino/SQLAlchemy's conditions for filtering.

    Example:
        A correct Gino's query is:
            User.query.where(
                and_(
                    User.role_id == 10,
                    User.location == "Singapore"
                )
            ).gino.all()

        The given `kwargs` is:
            {
                "role_id": 10,
                "location": "Singapore",
            }
        This function unpacks the given dictionary `kwargs`
        into `and_(*clauses)`.
    """
    return (getattr(model, k) == v for k, v in kwargs.items())


async def get_one(model, **kwargs):
    return (
        await model.query.where(and_(*dict_to_filter_args(model, **kwargs)))
        .limit(1)
        .gino.first()
    )


async def get_many(
    model,
    columns=None,
    after_id=None,
    limit=15,
    in_column=None,
    in_values=None,
    not_in_column=None,
    not_in_values=None,
    order_by="internal_id",
    descrease=False,
    offset=0,
    **kwargs,
):
    # Get the `internal_id` value from the starting row
    # And use it to query the next page of results
    last_internal_id = 0
    if after_id:
        row_of_after_id = await model.query.where(model.id == after_id).gino.first()
        if not row_of_after_id:
            raise_not_found_exception(model, **kwargs)

        last_internal_id = row_of_after_id.internal_id

    # Get certain columns only
    if columns:
        query = db.select([*(getattr(model, column) for column in columns)])
    else:
        query = model.query

    query = query.where(
        and_(
            *dict_to_filter_args(model, **kwargs),
            model.internal_id < last_internal_id
            if descrease and last_internal_id
            else model.internal_id > last_internal_id,
            getattr(model, in_column).in_(in_values)
            if in_column and in_values
            else True,
            getattr(model, not_in_column).notin_(not_in_values)
            if not_in_column and not_in_values
            else True,
        )
    )

    return (
        await query.order_by(
            desc(getattr(model, order_by)) if descrease else getattr(model, order_by)
        )
        .limit(limit)
        .offset(offset)
        .gino.all()
    )


async def get_flagged_chats_of_online_visitors(
    visitor_model,
    chat_model,
    *,
    in_column="visitor_id",
    in_values,
    order_by="updated_at",
    descrease=True,
    limit=15,
    **kwargs,
):
    # Join the tables to extract the user's info
    data = (
        await db.select(
            [
                *(getattr(chat_model, key) for key in chat_fields),
                *(getattr(visitor_model, key) for key in visitor_fields),
            ]
        )
        .select_from(
            visitor_model.join(chat_model, visitor_model.id == chat_model.visitor_id)
        )
        .where(
            and_(
                chat_model.severity_level != DEFAULT_SEVERITY_LEVEL_OF_CHAT,
                getattr(chat_model, in_column).in_(in_values)
                if in_column and in_values
                else True,
            )
        )
        .order_by(
            desc(getattr(chat_model, order_by))
            if descrease
            else getattr(chat_model, order_by)
        )
        .limit(limit)
        .gino.all()
    )

    result = []
    # Parse the message and sender
    for row in data:
        room = {}
        index = 0
        for key in chat_fields:
            room[key] = row[index]
            index += 1

        visitor = {}
        for key in visitor_fields:
            visitor[key] = row[index]
            index += 1

        # result.append({"room": room, "user": visitor})
        result.append({**room, **visitor})
    return result


async def get_messages(
    model,
    user,
    *,
    chat_id,
    before_id=None,
    after_id=None,
    limit=15,
    exclude=True,
    **kwargs,
):
    # Join the tables to extract the user's info
    query = db.select(
        [
            *(getattr(model, key) for key in message_fields),
            *(getattr(user, key) for key in user_fields),
        ]
    ).select_from(model.outerjoin(user, model.sender == user.id))

    # Get the `before_id` value from the starting row
    # And use it to query the next page of results
    if before_id or after_id:
        row_id = before_id or after_id
        row_of_before_id = await model.query.where(model.id == row_id).gino.first()
        if not row_of_before_id:
            raise_not_found_exception(model, **kwargs)

        last_sequence_num = row_of_before_id.sequence_num
        if after_id:
            query = query.where(
                and_(
                    model.chat_id == chat_id,
                    *dict_to_filter_args(model, **kwargs),
                    model.sequence_num > last_sequence_num
                    if exclude
                    else model.sequence_num >= last_sequence_num,
                )
            )
        else:  # before_id
            query = query.where(
                and_(
                    model.chat_id == chat_id,
                    *dict_to_filter_args(model, **kwargs),
                    model.sequence_num < last_sequence_num
                    if exclude
                    else model.sequence_num <= last_sequence_num,
                )
            )
    else:
        query = query.where(
            and_(model.chat_id == chat_id, *dict_to_filter_args(model, **kwargs))
        )

    if after_id:
        data = (
            await query.order_by(model.sequence_num, model.created_at)
            .limit(limit)
            .gino.all()
        )
    else:
        data = (await query.order_by(desc(model.sequence_num)).limit(limit).gino.all())[
            ::-1
        ]
    """
    result = await db.select([
        ChatMessage.sequence_num,
        ChatMessage.content,
        User.id,
        User.full_name,
    ]).select_from(ChatMessage.join(User, ChatMessage.sender == User.id)).gino.all()
    """
    result = []
    # Parse the message and sender
    for row in data:
        message = {}
        sender = None
        index = 0
        for key in message_fields:
            message[key] = row[index]
            index += 1

        if message["sender"]:
            sender = {}
            for key in user_fields:
                sender[key] = row[index]
                index += 1

        result.append({**message, "sender": sender})

    return result


async def get_bookmarked_visitors(
    visitor_model, bookmark_model, staff_id, *, limit=15, after_id=None, **kwargs
):
    # Get the `internal_id` value from the starting row
    # And use it to query the next page of results
    last_internal_id = None
    if after_id:
        row_of_after_id = await bookmark_model.query.where(
            bookmark_model.visitor_id == after_id
        ).gino.first()
        if not row_of_after_id:
            raise_not_found_exception(bookmark_model, visitor_id=after_id)

        last_internal_id = row_of_after_id.internal_id

    query = (
        db.select(
            [
                *(getattr(visitor_model, key) for key in visitor_fields),
                *(getattr(bookmark_model, key) for key in bookmark_fields),
            ]
        )
        .select_from(
            visitor_model.join(
                bookmark_model, visitor_model.id == bookmark_model.visitor_id
            )
        )
        .where(
            and_(
                bookmark_model.staff_id == staff_id,
                bookmark_model.is_bookmarked,
                bookmark_model.internal_id < last_internal_id
                if last_internal_id is not None
                else True,
            )
        )
        .order_by(desc(bookmark_model.internal_id))
        .limit(limit)
        .gino.all()
    )
    data = await query

    result = []
    # Parse the visitor
    for row in data:
        visitor_info = {}
        for key, val in zip(visitor_fields, row):
            visitor_info[key] = val

        result.append(visitor_info)

    return result


async def get_one_latest(model, order_by="internal_id", **kwargs):
    return (
        await model.query.where(and_(*dict_to_filter_args(model, **kwargs)))
        .order_by(desc(getattr(model, order_by)))
        .limit(1)
        .gino.first()
    )


async def get_one_oldest(model, order_by="internal_id", **kwargs):
    return (
        await model.query.where(and_(*dict_to_filter_args(model, **kwargs)))
        .order_by(getattr(model, order_by))
        .limit(1)
        .gino.first()
    )


async def get_many_with_count_and_group_by(
    model, *, columns, in_column=None, in_values=None
):
    return (
        await db.select(
            [*[getattr(model, column) for column in columns], db.func.count()]
        )
        .where(
            getattr(model, in_column).in_(in_values)
            if in_column and in_values
            else True
        )
        .group_by(*[getattr(model, column) for column in columns])
        .gino.all()
    )


async def get_top_unread_visitors(visitor_model, chat_model, staff_id, *, limit=15):
    # Add the visitor's table name as a suffix of the fields
    _visitor_fields = (
        "{}.{}".format(visitor_model.__tablename__, field) for field in visitor_fields
    )
    _chat_fields = (
        "{}.{}".format(chat_model.__tablename__, field) for field in chat_fields
    )
    data = (
        await db.status(
            db.text(
                """
                WITH seen_chats AS (
                	SELECT
                		distinct chat_message_seen.chat_id
                	FROM chat_message_seen
                	WHERE
                		chat_message_seen.staff_id = :staff_id
                ), most_recent_messages AS (
                	SELECT DISTINCT t.chat_id, chat_message.id as chat_msg_id
                	FROM (
                		SELECT
                				chat.id as chat_id,
                				MAX(chat_message.sequence_num) as max_sequence_num
                			FROM chat
                			JOIN chat_message on chat.id = chat_message.chat_id
                			GROUP BY chat.id
                	) t
                	JOIN chat_message ON chat_message.chat_id = t.chat_id
                	WHERE t.max_sequence_num = chat_message.sequence_num
                )
                SELECT {}
                FROM visitor
                JOIN chat ON chat.visitor_id = visitor.id
                LEFT OUTER JOIN chat_message_seen ON chat_message_seen.chat_id = chat.id
                WHERE
                	chat.id NOT IN (SELECT * FROM seen_chats)
                	OR chat_message_seen.last_seen_msg_id NOT IN (
                		SELECT most_recent_messages.chat_msg_id
                		FROM most_recent_messages
                		WHERE most_recent_messages.chat_id = chat_message_seen.chat_id
                	)
                    AND chat_message_seen.staff_id = :staff_id
                    AND EXISTS (
                        SELECT 1
                        FROM chat_message
                        WHERE chat_message.chat_id = chat.id
                    )
                ORDER BY chat.updated_at DESC, chat.created_at DESC
                LIMIT :limit
                """.format(
                    ", ".join(chain(_visitor_fields, _chat_fields))
                )
            ),
            {"staff_id": staff_id, "limit": limit},
        )
    )[1]

    result = []
    # Parse the visitors and chats
    for row in data:
        visitor = {}
        index = 0
        for key in visitor_fields:
            visitor[key] = row[index]
            index += 1

        chat_info = {}
        for key in chat_fields:
            chat_info[key] = row[index]
            index += 1

        result.append({"user": visitor, "room": chat_info})
    return result


async def get_visitors_with_most_recent_chats(
    chat_model,
    chat_message,
    visitor,
    staff,
    requester: dict,
    *,
    page=0,
    limit=15,
    **kwargs,
):
    """Return the visitors with the most recent chats to your organisation."""

    # Join the tables to get the staffs
    query = db.select(
        [
            # *(getattr(visitor, key) for key in visitor_fields),
            visitor.id,
            func.max(chat_message.created_at).label("max_created_at"),
        ]
    ).select_from(
        staff.join(chat_message, chat_message.sender == staff.id)
        .join(chat_model, chat_model.id == chat_message.chat_id)
        .join(visitor, chat_model.visitor_id == visitor.id)
    )

    query = query.where(
        and_(
            staff.organisation_id == requester["organisation_id"],
            *dict_to_filter_args(staff, **kwargs),
        )
    ).group_by(visitor.id)

    # Execute the query
    visitor_alias = visitor.alias("alias_visitor")
    temp = query.alias("alias_visitor")
    data = (
        await db.select([*(getattr(visitor, key) for key in visitor_fields)])
        .select_from(visitor.join(temp, visitor_alias.id == visitor.id))
        .order_by(desc("max_created_at"))
        .limit(limit)
        .offset(page * limit)
        .gino.all()
    )

    result = []
    # Parse the visitors
    for row in data:
        visitor_data = {key: value for key, value in zip(visitor_fields, row)}
        result.append(visitor_data)

    return result


@in_transaction
async def create_one(model, **kwargs):
    try:
        return await model(**kwargs).create()
    except UniqueViolationError as err:
        raise DuplicatedError(err.as_dict())


@in_transaction
async def update_one(row, **kwargs):
    if not kwargs:
        return row

    await row.update(**kwargs).apply()
    return row


@in_transaction
async def update_many(model, get_kwargs, update_kwargs):
    status: Tuple[str, list] = await model.update.values(**update_kwargs).where(
        and_(*and_(*dict_to_filter_args(model, **get_kwargs)))
    ).gino.status()
    return status[0]


@in_transaction
async def delete_many(model, **kwargs):
    status: Tuple[str, list] = await model.delete.where(
        and_(*dict_to_filter_args(model, **kwargs))
    ).gino.status()
    return status[0]


@in_transaction
async def execute(sql_query, **kwargs):
    return (await db.status(db.text(sql_query), kwargs))[1]
