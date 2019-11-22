from celery import Celery

from ora_backend.config import CELERY_BROKER_URL
from ora_backend.templates.emails import email_template, email_without_button_template
from ora_backend.utils.emails import send_email as _send_email

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
def send_email_for_new_assigned_chat(receivers: list, visitor: dict):
    """Send an email to all supervisors about the new message, when no one is online."""
    if not receivers:
        return None

    email_subject = "You have been assigned to chat with {}!".format(visitor["name"])
    title = "You have been assigned to chat with <strong>{}</strong>!".format(
        visitor["name"]
    )
    content = "Someone needs your help!"
    button = "Reply Now!"
    mail_content = email_template(title=title, content=content, button=button)

    status_code = _send_email(
        receivers=receivers,
        subject="[New Chat] {}".format(email_subject),
        content=mail_content.strip(),
    )
    return status_code


@celery_app.task
def send_email_for_being_removed_from_chat(receivers: list, visitor: dict):
    """Send an email to all supervisors about the new message, when no one is online."""
    if not receivers:
        return None

    email_subject = "You have been removed from the chat with visitor {}!".format(
        visitor["name"]
    )
    title = "You have been removed from the chat with visitor <strong>{}</strong>!".format(
        visitor["name"]
    )
    content = "For more information, please contact your supervisor."
    mail_content = email_without_button_template(title=title, content=content)

    status_code = _send_email(
        receivers=receivers,
        subject="[Removed From Chat] {}".format(email_subject),
        content=mail_content.strip(),
    )
    return status_code


@celery_app.task
def send_email_for_flagged_chat(receivers: list, visitor: dict):
    """Send an email to all supervisors about the new message, when no one is online."""
    # if not receivers:
    #     return None
    receivers = []

    email_subject = "A staff has flagged the chat with visitor {}!".format(
        visitor["name"]
    )
    title = "A staff has flagged the chat with visitor <strong>{}</strong>!".format(
        visitor["name"]
    )
    content = """A volunteer needs your expertise and guidance.<br/>
        Click the button below to attend to the chat.""".strip()
    button = "View Now!"
    mail_content = email_template(title=title, content=content, button=button)

    status_code = _send_email(
        receivers=receivers,
        subject="[Flagged Chat] {}".format(email_subject),
        content=mail_content.strip(),
    )
    return status_code
