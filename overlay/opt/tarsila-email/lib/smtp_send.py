"""Envio SMTP."""
import base64
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import config, imap_sync


def send_mail(to_addrs: list, subject: str, body: str,
              attachments: list | None = None, html: bool = False) -> None:
    cfg = config.load()
    msg = MIMEMultipart()
    msg["From"] = f'{cfg.get("name", "")} <{cfg["email"]}>'.strip()
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject or "(sem assunto)"
    subtype = "html" if html else "plain"
    msg.attach(MIMEText(body or "", subtype, "utf-8"))
    for att in attachments or []:
        nome = att.get("name", "anexo")
        data = base64.b64decode(att.get("data", ""))
        part = MIMEBase("application", "octet-stream")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{nome}"')
        msg.attach(part)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], context=ctx,
                          timeout=30) as smtp:
        smtp.login(cfg["email"], config.password(cfg))
        smtp.send_message(msg)
    imap_sync.sync_folder_by_id("sent", limit=10)
