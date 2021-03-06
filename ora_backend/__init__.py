from datetime import timedelta
import logging

from aiocache import RedisCache
from aiocache.serializers import JsonSerializer
from asyncpg.exceptions import UniqueViolationError
from gino.ext.sanic import Gino
from sanic import Blueprint, Sanic
from sanic.exceptions import SanicException
from sanic.response import text
from sanic_jwt_extended import JWTManager
from sanic_cors import CORS
from sanic_limiter import Limiter, get_remote_address
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sanic import SanicIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


from ora_backend.config import (
    JWT_SECRET_KEY,
    SANIC_CONFIG,
    CORS_ORIGINS,
    SENTRY_DSN,
    MODE,
    CELERY_BROKER_PASSWORD,
)
from ora_backend.constants import UNCLAIMED_CHATS_PREFIX

# Init Sentry before app creation
if SENTRY_DSN:
    sentry_init(
        dsn=SENTRY_DSN,
        integrations=[
            CeleryIntegration(),
            RedisIntegration(),
            SanicIntegration(),
            SqlalchemyIntegration(),
        ],
        request_bodies="always",
        send_default_pii=True,
    )

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
redis_port = 6379
if MODE == "testing":
    redis_port = 63791
elif MODE == "development":
    redis_port = 63790
cache = RedisCache(
    serializer=JsonSerializer(),
    password=CELERY_BROKER_PASSWORD,
    pool_min_size=3,
    port=redis_port,
)

# Initialize the DB before doing anything else
# to avoid circular importing
db.init_app(app)
JWTManager(app)
CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

# logging.getLogger("sanic_cors").level = logging.DEBUG

# Register the limiter
# from ora_backend.utils.limiter import get_user_id_or_ip_addr
limiter = Limiter(app, global_limits=["200/minute"], key_func=get_remote_address)

# Register the routes/views
from ora_backend.views.urls import blueprints

app.blueprint(blueprints)

# Register error handlers
from ora_backend.exceptions import sanic_error_handler, unique_violation_error_handler

app.error_handler.add(SanicException, sanic_error_handler)
app.error_handler.add(UniqueViolationError, unique_violation_error_handler)


async def init_plugins(app, loop):
    await db.gino.create_all()
    # await cache.clear()


# Register the listeners
app.register_listener(init_plugins, "after_server_start")

# Register background tasks
from ora_backend.tasks.assign import check_for_reassign_chats_every_half_hour

app.add_task(check_for_reassign_chats_every_half_hour())


# Register Prometheus
try:
    # import prometheus_client as prometheus
    from sanic_prometheus import monitor
except Exception:
    pass
else:
    if MODE == "production":
        # Adds /metrics endpoint to the Sanic server
        monitor(
            app,
            endpoint_type="url",
            latency_buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 10, 30, 60, 120],
        ).expose_endpoint()
