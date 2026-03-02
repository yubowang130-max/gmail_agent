from __future__ import annotations

from dataclasses import dataclass
import email
from email.utils import parseaddr
import re
from typing import Optional

from mail.imap_client import RawMail, decode_mime_text


@dataclass
class ParsedMail:
    message_id: str
    uid: str
    sender_name: str
    sender_email: str
    subject: str
    date_iso: str
    body_preview: str


def _extract_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in disposition.lower():
                continue
            if content_type in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    text = payload.decode(charset, errors="ignore")
                except Exception:
                    text = payload.decode("utf-8", errors="ignore")
                if content_type == "text/html":
                    text = re.sub(r"<[^>]+>", " ", text)
                parts.append(text)
        return "\n".join(parts)

    payload = msg.get_payload(decode=True)
    if payload is None:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="ignore")
    except Exception:
        return payload.decode("utf-8", errors="ignore")


def parse_raw_mail(raw_mail: RawMail, max_preview_chars: int = 500) -> ParsedMail:
    msg = email.message_from_bytes(raw_mail.raw_bytes)
    sender_name, sender_email = parseaddr(msg.get("From") or "")
    subject = decode_mime_text(msg.get("Subject"))

    text = _extract_text(msg)
    text = re.sub(r"\s+", " ", text).strip()
    preview = text[:max_preview_chars]

    return ParsedMail(
        message_id=raw_mail.message_id,
        uid=raw_mail.uid,
        sender_name=decode_mime_text(sender_name),
        sender_email=sender_email,
        subject=subject,
        date_iso=raw_mail.received_at.isoformat(),
        body_preview=preview,
    )
