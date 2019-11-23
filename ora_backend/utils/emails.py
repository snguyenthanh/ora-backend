from os import environ

from celery import states
from celery.exceptions import Ignore
from http.client import IncompleteRead
from urllib.error import HTTPError
from python_http_client.exceptions import UnauthorizedError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail, Personalization


# if "SENDGRID_API_KEY" not in environ:
# raise KeyError("Missing environmental variable SENDGRID_API_KEY")

SENDGRID_API_KEY = environ.get("SENDGRID_API_KEY")

if SENDGRID_API_KEY:
    sg = SendGridAPIClient(SENDGRID_API_KEY)
else:
    sg = None


def mark_task_as_failed(task, reason=None):
    reason = reason or "Task failed"
    task.update_state(state=states.FAILURE, meta=reason)

    # ignore the task so no other state is recorded
    raise Ignore()


def send_email(*, receivers: list, subject: str, content: str, celery_task=None):
    """
    Kwargs:
        receivers [List[Str]]:
            A list of emails to send the mail.

        subject [Str]:
            The subject of the mail

        content [Str]:
            The HTML content of the mail
    """
    if not sg or not receivers:
        return None

    message = Mail(
        from_email=("nus.chatwithora@gmail.com", "Ora"),
        # to_emails="thanhson16198@gmail.com",
        subject=subject,
        html_content=content,
        # subject='Sending with Twilio SendGrid is Fun',
        # html_content='<strong>and easy to do anywhere, even with Python</strong>'
    )

    # Add the receivers
    to_list = Personalization()
    for recv in receivers:
        # to_list.add_to(Email("EMAIL ADDRESS"))
        to_list.add_to(Email(recv))

    # Inject the receivers to the email
    message.add_personalization(to_list)

    status_code = 500
    try:
        response = sg.send(message)
        status_code = response.status_code
    except HTTPError as exc:
        status_code = 401
        if celery_task:
            mark_task_as_failed(celery_task, reason=str(exc))
    except IncompleteRead as exc:
        status_code = 401
        if celery_task:
            mark_task_as_failed(celery_task, reason=str(exc))
    except UnauthorizedError as exc:
        status_code = 401
        if celery_task:
            mark_task_as_failed(celery_task, reason=str(exc))

    # return {
    #     "status_code": response.status_code,
    #     "body": response.body,
    #     "headers": response.headers,
    # }
    return status_code
