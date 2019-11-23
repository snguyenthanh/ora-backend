from sanic_limiter import get_remote_address
from sanic_jwt_extended.decorators import get_jwt_data

from ora_backend import app
from ora_backend.utils.auth import get_token_from_request
from ora_backend.utils.crypto import unsign_str


async def get_user_id_or_ip_addr(request):
    requester = None
    try:
        token = unsign_str(request.cookies["access_token"].strip())
        jwt_token_data = await get_jwt_data(app, token)
        requester = jwt_token_data["identity"]
    except Exception:
        requester = None

    if requester:
        return requester["id"]

    return get_remote_address(request)
