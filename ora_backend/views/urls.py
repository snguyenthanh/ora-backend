from sanic import Blueprint

root_blueprint = Blueprint("root")
user_blueprint = Blueprint("user", url_prefix="/users")
visitor_blueprint = Blueprint("visitor", url_prefix="/visitors")
setting_blueprint = Blueprint("setting", url_prefix="/settings")

# Import the blueprints that have views added to it
from ora_backend.views.root import blueprint as root
from ora_backend.views.user import blueprint as user
from ora_backend.views.visitor import blueprint as visitor
from ora_backend.views.setting import blueprint as setting

blueprints = Blueprint.group(root, user, visitor, setting)
