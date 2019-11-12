from os import environ

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail, Personalization


if "SENDGRID_API_KEY" not in environ:
    raise KeyError("Missing environmental variable SENDGRID_API_KEY")

sg = SendGridAPIClient(environ["SENDGRID_API_KEY"])


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
    message = Mail(
        from_email=("nus.chatwithora@gmail.com", "Ora"),
        to_emails="thanhson16198@gmail.com",
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

    response = sg.send(message)
    # return {
    #     "status_code": response.status_code,
    #     "body": response.body,
    #     "headers": response.headers,
    # }
    return response.status_code

# send_email(
#     receivers=["thanhson16198@gmail.com", "e0072396@u.nus.edu"],
#     subject="Another subject",
#     content="<strong>and easy to do anywhere, even with Python</strong>",
# )
