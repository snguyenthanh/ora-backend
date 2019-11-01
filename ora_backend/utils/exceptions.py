from sanic.exceptions import NotFound, Forbidden

from ora_backend.constants import ROLES


def raise_not_found_exception(model, **kwargs):
    message = "Unable to find {}".format(model.__name__)
    if kwargs:
        message += " with " + ", ".join(
            "{!s}={!r}".format(key, val) for (key, val) in kwargs.items()
        )
    raise NotFound(message)


def raise_permission_exception():
    raise Forbidden("You are not allowed to perform this action.")


def raise_role_authorization_exception(target_role_id, action: str = None):
    # action = action or "perform this action"
    # if ROLES[target_role_id] == "admin":
    #     raise Forbidden("Please contact the service provider" " to {}.".format(action))
    action = action or "create"
    raise Forbidden(
        "Only {} and upper are allowed to {} {} accounts.".format(
            ROLES[target_role_id - 1], action, ROLES[target_role_id]
        )
    )
