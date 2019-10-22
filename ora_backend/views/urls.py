from sanic import Blueprint

root_blueprint = Blueprint("root")
user_blueprint = Blueprint("user", url_prefix="/users")

# Import the blueprints that have views added to it
from ora_backend.views.root import blueprint as root
from ora_backend.views.user import blueprint as user

blueprints = Blueprint.group(root, user)
