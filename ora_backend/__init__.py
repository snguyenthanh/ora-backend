from datetime import timedelta
import logging

from aiocache import Cache
from aiocache.serializers import JsonSerializer
from gino.ext.sanic import Gino
from sanic import Blueprint, Sanic
from sanic.exceptions import SanicException
from sanic_jwt_extended import JWTManager
from sanic_cors import CORS
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.sanic import SanicIntegration

from ora_backend.config import JWT_SECRET_KEY, SANIC_CONFIG, CORS_ORIGINS, SENTRY_DSN
from ora_backend.constants import UNCLAIMED_CHATS_PREFIX

# Note: Gino doesn't auto-generate any new changes in the schema
# Use alembic to apply new changes to the db
# (Refer to scripts/migration.sh)
db = Gino()

app = Sanic(__name__)

app.config.update(SANIC_CONFIG)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
app.config["JWT_TOKEN_LOCATION"] = "cookies"
app.config["JWT_ERROR_MESSAGE_KEY"] = "error"
app.config["CORS_AUTOMATIC_OPTIONS"] = True
app.config["CORS_SUPPORTS_CREDENTIALS"] = True

# Construct an in-memory storage
cache = Cache(serializer=JsonSerializer())

# Initialize the DB before doing anything else
# to avoid circular importing
db.init_app(app)
JWTManager(app)
CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

if SENTRY_DSN:
    sentry_init(dsn=SENTRY_DSN, integrations=[SanicIntegration()])

# logging.getLogger("sanic_cors").level = logging.DEBUG


# Register the routes/views
from ora_backend.views.urls import blueprints

app.blueprint(blueprints)

# Register error handlers
from ora_backend.exceptions import sanic_error_handler

app.error_handler.add(SanicException, sanic_error_handler)

# Register SocketIO
# from ora_backend.views.chat_socketio import app


async def init_plugins(app, loop):
    await db.gino.create_all()
    # await cache.clear()


# Register the listeners
app.register_listener(init_plugins, "after_server_start")
