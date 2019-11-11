from time import sleep
from celery import Celery

app = Celery("tasks", backend="redis://localhost", broker="amqp://localhost")


@app.task(bind=True)
def add(self, x, y):
    sleep(2)
    self.update_state(state="PROGRESS", meta={"progress": 50})
    sleep(2)
    self.update_state(state="PROGRESS", meta={"progress": 90})
    sleep(2)
    return x + y
