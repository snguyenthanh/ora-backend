from os import environ
import ssl

from sanic.websocket import WebSocketProtocol

from ora_backend.config.db import DB_CONFIG

MODE = environ.get("MODE", "development").lower()

if MODE == "production":
    JWT_SECRET_KEY = environ["JWT_SECRET_KEY"]
    PASSWORD_SALT = environ["PASSWORD_SALT"]
    COOKIE_SIGN_KEY = environ["COOKIE_SIGN_KEY"]
else:
    # These are dummy values for dev and testing
    # Actual production servers have kept these info as env variables
    JWT_SECRET_KEY = "oi123n1k231kloiqwescqklwn"
    PASSWORD_SALT = "07facbc897aab311d1e72a1cb1c131616b68868921674ed56ade6ffcef18ee6e"
    COOKIE_SIGN_KEY = "b116f07be8e441861bd59bdf0bf88727c578ed9dba62c1bc6c1c00863f458721"

SANIC_BASE_CONFIG = {
    "REQUEST_TIMEOUT": 60 * 5,
    "RESPONSE_TIMEOUT": 60 * 5,
    "GRACEFUL_SHUTDOWN_TIMEOUT": 60 * 5,
    "KEEP_ALIVE_TIMEOUT": 10,
}

SENTRY_DSN = environ.get("SENTRY_DSN")

DB_URL = environ.get("DB_URL")
if DB_URL:
    SANIC_CONFIG = {"DB_DSN": DB_URL, **SANIC_BASE_CONFIG}
else:
    SANIC_CONFIG = {**DB_CONFIG, **SANIC_BASE_CONFIG}

# Add CA cert to config
DB_CERT = environ.get("DB_CERT")
if DB_CERT:
    ssl_ctx = ssl.create_default_context(cafile=DB_CERT)
    SANIC_CONFIG["DB_SSL"] = ssl_ctx

SANIC_RUN_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    # "debug": MODE != "production",
    "debug": True,
    "access_log": MODE != "production",
    "workers": 3,
}

SOCKETIO_RUN_CONFIG = {
    "host": "0.0.0.0",
    "port": 8080,
    "debug": MODE != "production",
    "access_log": MODE != "production",
    "workers": 1,
    "protocol": WebSocketProtocol,
}

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ora-frontend.firebaseapp.com",
    "https://chatwithora.com",
    "https://wwww.chatwithora.com",
]

# Celery
CELERY_BROKER_IP = environ["CELERY_BROKER_IP"]
CELERY_USER = environ["CELERY_USER"]
CELERY_USER_PASSWORD = environ["CELERY_USER_PASSWORD"]
CELERY_VHOST = environ["CELERY_VHOST"]
CELERY_BROKER_URL = "amqp://{}:{}@{}:5672/{}".format(
    CELERY_USER, CELERY_USER_PASSWORD, CELERY_BROKER_IP, CELERY_VHOST
)
