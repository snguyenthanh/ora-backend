from time import sleep
from celery import Celery

from ora_backend.config import CELERY_BROKER_URL, CELERY_BROKER_IP

celery_app = Celery(
    "tasks",
    backend="redis://{}:6379/0".format(CELERY_BROKER_IP),
    broker=CELERY_BROKER_URL,
)
# celery_app = Celery("tasks", backend="amqp", broker="amqp://localhost")


@celery_app.task(bind=True)
def add(self, x, y):
    sleep(2)
    self.update_state(state="PROGRESS", meta={"progress": 50})
    sleep(2)
    self.update_state(state="PROGRESS", meta={"progress": 90})
    sleep(2)
    return x + y
