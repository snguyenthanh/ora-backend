from hashlib import sha512

from itsdangerous import Signer as _Signer
from sanic.exceptions import InvalidUsage, Unauthorized

from ora_backend.config import PASSWORD_SALT, COOKIE_SIGN_KEY

signer = _Signer(COOKIE_SIGN_KEY)


def sign_value(value: str):
    return signer.sign(value)


def unsign_value(value: str):
    if not signer.validate(value):
        raise Unauthorized("Invalid cookie.")

    return signer.unsign(value)


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
