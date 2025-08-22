import os


def send_email(to_addr: str, subject: str, body: str):
    host = os.getenv("SMTP_HOST")
    if not host:
        return "SMTP not configured"
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_FROM", os.getenv("SMTP_USERNAME", "noreply@example.com"))
    msg["To"] = to_addr

    server = smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587)))
    server.starttls()
    server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
    server.send_message(msg)
    server.quit()
    return "sent"


