from os import environ

from http.client import IncompleteRead
from urllib.error import HTTPError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail, Personalization


# if "SENDGRID_API_KEY" not in environ:
# raise KeyError("Missing environmental variable SENDGRID_API_KEY")

SENDGRID_API_KEY = environ.get("SENDGRID_API_KEY")

if SENDGRID_API_KEY:
    sg = SendGridAPIClient(SENDGRID_API_KEY)
else:
    sg = None


def send_email(*, receivers: list, subject: str, content: str):
    """
    Kwargs:
        receivers [List[Str]]:
            A list of emails to send the mail.

        subject [Str]:
            The subject of the mail

        content [Str]:
            The HTML content of the mail
    """
    if not sg:
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
    # to_list.add_to(Email("thanhson16198@gmail.com"))
    # to_list.add_to(Email("e0072396@u.nus.edu"))
    # to_list.add_to(Email("jasontjakra@gmail.com"))
    for recv in receivers:
        # to_list.add_to(Email("EMAIL ADDRESS"))
        to_list.add_to(Email(recv))

    # Inject the receivers to the email
    message.add_personalization(to_list)

    status_code = 500
    try:
        response = sg.send(message)
        status_code = response.status_code
    except (HTTPError, IncompleteRead):
        status_code = 401

    # return {
    #     "status_code": response.status_code,
    #     "body": response.body,
    #     "headers": response.headers,
    # }
    return status_code


# send_email(
#     receivers=["thanhson16198@gmail.com", "e0072396@u.nus.edu"],
#     subject="Another subject",
#     content="<strong>and easy to do anywhere, even with Python</strong>",
# )
