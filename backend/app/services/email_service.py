import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import settings

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, body: str):
        message = Mail(
            from_email=settings.SENDER_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return {"status": response.status_code}

    @staticmethod
    def send_bulk_emails(recipients: list[str], subject: str, body: str):
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        messages = []
        for email in recipients:
            msg = Mail(
                from_email=settings.SENDER_EMAIL,
                to_emails=email,
                subject=subject,
                html_content=body,
            )
            messages.append(msg)
        results = []
        for msg in messages:
            response = sg.send(msg)
            results.append({"email": msg.to[0].email, "status": response.status_code})
        return {"sent": results}
