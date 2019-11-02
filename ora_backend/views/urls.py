from sanic import Blueprint

root_blueprint = Blueprint("root")
user_blueprint = Blueprint("user", url_prefix="/users")
visitor_blueprint = Blueprint("visitor", url_prefix="/visitors")
chat_blueprint = Blueprint("chat", url_prefix="/chats")

# Import the blueprints that have views added to it
from ora_backend.views.root import blueprint as root
from ora_backend.views.user import blueprint as user
from ora_backend.views.visitor import blueprint as visitor
from ora_backend.views.chat import blueprint as chat

blueprints = Blueprint.group(root, user, visitor, chat)
