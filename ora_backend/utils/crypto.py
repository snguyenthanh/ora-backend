from hashlib import sha512

from itsdangerous import Signer as _Signer
from sanic.exceptions import InvalidUsage, Unauthorized

from ora_backend.config import PASSWORD_SALT, COOKIE_SIGN_KEY

str_signer = _Signer(COOKIE_SIGN_KEY, salt="token-signing")


def sign_str(value: str):
    return str_signer.sign(value).decode("utf-8")


def unsign_str(value: str):
    if not str_signer.validate(value):
        raise Unauthorized("Invalid cookie.")

    return str_signer.unsign(value)


def hash_password(password: str) -> str:
    salted = password + PASSWORD_SALT
    return sha512(salted.encode("utf8")).hexdigest()


def validate_password_strength(password: str):
    """
    Validate if the password is strong enough.

    Password strength rules:
    - Minimum length: 8 characters
    - Has at least 1 number
    """
    if len(password) >= 8 and any(char.isdigit() for char in password):
        return

    raise InvalidUsage(
        {
            "password": [
                "Your password is not strong enough. "
                "Ensure it has at least 8 characters, and at least 1 number."
            ]
        }
    )
