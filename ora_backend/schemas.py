"""
Schemas are Cerberus rules used for validation of user input
and serializing results to return to users.
"""

# Conversion
to_boolean = lambda v: v.lower() in {"true", "1"} if isinstance(v, str) else bool(v)
to_lowercase = lambda text: text.lower()

# Common rules
is_integer = {"type": "integer", "coerce": int, "nullable": False, "empty": False}
is_unsigned_integer = {**is_integer, "min": 0}
is_unsigned_integer_with_max = {**is_unsigned_integer, "max": 100}
is_nullable_integer = {"type": "integer", "coerce": int}
is_required_integer = {**is_integer, "required": True}
is_required_unsigned_integer = {**is_unsigned_integer, "required": True}
is_boolean = {
    "type": "boolean",
    "coerce": to_boolean,
    "nullable": False,
    "empty": False,
}
is_string = {"type": "string", "empty": False, "nullable": False}
is_string_lowercase = {**is_string, "coerce": to_lowercase}
is_optional_string = {"type": "string"}
is_required_string = {**is_string, "required": True}
is_required_string_lowercase = {**is_required_string, "coerce": to_lowercase}
is_string_list = {"type": "list", "schema": is_string}
is_required_string_list = {
    "type": "list",
    "required": True,
    "schema": is_required_string,
}
is_json_list = {"type": "list", "schema": {"type": "dict"}}


# Schemas

CHAT_READ_SCHEMA = {
    "id": is_string,
    "visitor_id": is_string,
    "tags": is_json_list,
    "severity_level": is_unsigned_integer,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

CHAT_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "visitor_id": is_required_string,
    "tags": is_json_list,
    "severity_level": is_unsigned_integer,
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

CHAT_MESSAGE_READ_SCHEMA = {
    "id": is_string,
    "sequence_num": is_unsigned_integer,
    "type_id": is_integer,
    "chat_id": is_string,
    "sender": is_string,
    "content": {"type": "dict"},
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

CHAT_MESSAGE_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "sequence_num": {"readonly": True},
    "type_id": is_integer,
    "chat_id": is_required_string,
    "sender": is_string,
    "content": {"type": "dict"},
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

VISITOR_READ_SCHEMA = {
    "id": is_string,
    "name": {"type": "string"},
    "email": {"type": "string"},
    "password": {"readonly": True},
    "is_anonymous": is_boolean,
    "disabled": is_boolean,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

VISITOR_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "name": is_required_string,
    "email": is_required_string_lowercase,
    "password": {**is_required_string, "minlength": 8, "maxlength": 128},
    "is_anonymous": is_boolean,
    "disabled": is_boolean,
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

USER_READ_SCHEMA = {
    "id": is_string,
    "internal_id": is_integer,
    "full_name": is_string,
    "display_name": is_string,
    "email": {"type": "string"},
    "password": {"readonly": True},
    "role_id": is_integer,
    "organisation_id": is_string,
    "disabled": is_boolean,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

USER_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "full_name": is_required_string,
    "display_name": {"type": "string"},
    "email": is_required_string_lowercase,
    "password": {**is_required_string, "minlength": 8, "maxlength": 128},
    "role_id": is_integer,
    "organisation_id": {"readonly": True},
    "disabled": is_boolean,
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

USER_LOGIN_SCHEMA = {"email": is_required_string, "password": is_required_string}

ANONYMOUS_LOGIN_SCHEMA = {"name": is_required_string}

ORGANISATION_READ_SCHEMA = {
    "id": is_string,
    "name": is_string,
    "disabled": is_boolean,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

CHAT_MESSAGE_SEEN_READ_SCHEMA = {
    "id": is_string,
    "staff_id": is_string,
    "chat_id": is_string,
    "last_seen_msg_id": is_string,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

CHAT_MESSAGE_SEEN_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "staff_id": is_required_string,
    "chat_id": is_required_string,
    "last_seen_msg_id": is_required_string,
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

BOOKMARK_VISITOR_READ_SCHEMA = {
    "id": is_string,
    "staff_id": is_string,
    "visitor_id": is_string,
    "is_bookmarked": is_boolean,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

BOOKMARK_VISITOR_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "staff_id": is_required_string,
    "visitor_id": is_required_string,
    "is_bookmarked": is_boolean,
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

NOTIFICATION_STAFF_READ_SCHEMA = {
    "id": is_string,
    "staff_id": is_string,
    "content": {"type": "dict"},
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

NOTIFICATION_STAFF_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "staff_id": {"readonly": True},
    "content": {"type": "dict"},
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}

SETTING_READ_SCHEMA = {
    "id": is_string,
    "key": is_string,
    "value": is_integer,
    "created_at": is_unsigned_integer,
    "updated_at": is_unsigned_integer,
}

SETTING_WRITE_SCHEMA = {
    "id": {"readonly": True},
    "key": {"readonly": True},
    "value": is_required_integer,
    "created_at": {"readonly": True},
    "updated_at": {"readonly": True},
}


# INJECTED SCHEMAS

GLOBAL_SCHEMA = {"internal_id": {"readonly": True}}
QUERY_PARAM_READ_SCHEMA = {"after_id": is_string, "limit": is_unsigned_integer_with_max}
QUERY_PARAM_GET_VISITORS = {
    "page": is_unsigned_integer_with_max,
    "limit": is_unsigned_integer_with_max,
}

## INJECT FIELDS TO SCHEMAS
variables = locals()
for var_name in list(variables.keys()):
    inject_dict = {}

    if var_name.endswith("_SCHEMA"):
        inject_dict.update(GLOBAL_SCHEMA)
        if var_name.endswith("_READ_SCHEMA"):
            inject_dict.update(QUERY_PARAM_READ_SCHEMA)

        # Update the variable
        variables[var_name].update(inject_dict)


"""
The format for keys in `schemas` is
<tablename>_read or <tablename>_write

Please strictly follow this format
as several utils function get the schema by
adding '_read' after model.__tablename__

Except for user_login.
"""
schemas = {
    "chat_read": CHAT_READ_SCHEMA,
    "chat_write": CHAT_WRITE_SCHEMA,
    "chat_message_read": CHAT_MESSAGE_READ_SCHEMA,
    "chat_message_write": CHAT_MESSAGE_WRITE_SCHEMA,
    "visitor_read": VISITOR_READ_SCHEMA,
    "visitor_write": VISITOR_WRITE_SCHEMA,
    "user_read": USER_READ_SCHEMA,
    "user_write": USER_WRITE_SCHEMA,
    "user_login": USER_LOGIN_SCHEMA,
    "anonymous_login": ANONYMOUS_LOGIN_SCHEMA,
    "organisation_read": ORGANISATION_READ_SCHEMA,
    "query_params_get_visitors": QUERY_PARAM_GET_VISITORS,
    "chat_message_seen_read": CHAT_MESSAGE_SEEN_READ_SCHEMA,
    "chat_message_seen_write": CHAT_MESSAGE_SEEN_WRITE_SCHEMA,
    "bookmark_visitor_read": BOOKMARK_VISITOR_READ_SCHEMA,
    "bookmark_visitor_write": BOOKMARK_VISITOR_WRITE_SCHEMA,
    "notification_staff_read": NOTIFICATION_STAFF_READ_SCHEMA,
    "notification_staff_write": NOTIFICATION_STAFF_WRITE_SCHEMA,
    "setting_read": SETTING_READ_SCHEMA,
    "setting_write": SETTING_WRITE_SCHEMA,
}
