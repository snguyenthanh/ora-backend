from time import sleep
from celery import Celery

from ora_backend.config import CELERY_BROKER_URL
from ora_backend.utils.emails import send_email as _send_email


# if WORKER_TYPE == "celery":
#     celery_app = Celery(
#         "tasks",
#         # backend="redis://http://{}:6379/0".format(CELERY_BROKER_IP),
#         # backend=CELERY_BROKER_URL,
#         # broker=CELERY_BROKER_URL,
#         backend="redis://localhost",
#         broker="redis://localhost",
#     )
# else:
celery_app = Celery(
    "tasks",
    # backend="redis://http://{}:6379/0".format(CELERY_BROKER_IP),
    backend=CELERY_BROKER_URL,
    broker=CELERY_BROKER_URL,
    # backend="redis://localhost",
    # broker="redis://localhost",
)
# celery_app = Celery("tasks", backend="amqp", broker="amqp://localhost")


# @celery_app.task(bind=True)
# def add(self, x, y):
#     sleep(2)
#     self.update_state(state="PROGRESS", meta={"progress": 50})
#     sleep(2)
#     self.update_state(state="PROGRESS", meta={"progress": 90})
#     sleep(2)
#     return x + y


@celery_app.task
def send_email(receivers: list, visitor: dict, visitor_msg):
    """Send an email to all supervisors about the new message, when no one is online."""
    if not receivers:
        return None

    if visitor_msg:
        if isinstance(visitor_msg, dict):
            visitor_msg = visitor_msg.get("content")

        mail_content = """
        While no staffs are online, visitor <strong>{}</strong> has sent a message: <br/>
        <blockquote>{}</blockquote>
        """.format(
            visitor["name"], visitor_msg
        )
    else:
        mail_content = """
            Visitor <strong>{}</strong> has sent a message while no staffs are online.
        """.format(
            visitor["name"]
        )

    print("CELERY_SEND")
    print(receivers)
    print(mail_content)
    status_code = _send_email(
        receivers=receivers,
        subject="A visitor sent a message while no staffs are online",
        content=mail_content.strip(),
    )
    return status_code
