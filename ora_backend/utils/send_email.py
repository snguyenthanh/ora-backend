SENDGRID_API_KEY = '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'

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email=('nus.chatwithora@gmail.com', "Ora"),
    to_emails='thanhson16198@gmail.com',
    subject='Sending with Twilio SendGrid is Fun',
    html_content='<strong>and easy to do anywhere, even with Python</strong>')

sg = SendGridAPIClient(SENDGRID_API_KEY)
response = sg.send(message)
print(response)
print(response.status_code)
print(response.body)
print(response.headers)
