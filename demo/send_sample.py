"""Sends one phishing and one legitimate mail to alice, to test the pipeline before GoPhish is ready."""
import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))


def send(frm, to, subj, body, auth=None, reply_to=None):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, to, subj
    if reply_to:
        m["Reply-To"] = reply_to
    if auth:
        m["Authentication-Results"] = auth
    m.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.send_message(m)


if __name__ == "__main__":
    send('"Corp IT Support" <it@corp-verify.test>', "alice@corp.local",
         "Action required: verify your Corp account",
         "Your password expires within 24 hours. Verify immediately: "
         "http://secure-login.corp-verify.test/login",
         auth="mx.corp.local; spf=fail; dkim=none; dmarc=fail", reply_to="help@mail-helpdesk.test")
    send("hr@corp.local", "alice@corp.local", "Team meeting Thursday",
         "See the agenda here: https://github.com/corp/agenda",
         auth="mx.corp.local; spf=pass; dkim=pass; dmarc=pass")
    print("sent 2 sample mails to alice@corp.local")
