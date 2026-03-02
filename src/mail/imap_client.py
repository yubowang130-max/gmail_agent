from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import email
from email.header import decode_header, make_header
import imaplib
import os
from typing import List, Optional


@dataclass
class RawMail:
    uid: str
    message_id: str
    received_at: datetime
    raw_bytes: bytes


class NeteaseImapClient:
    def __init__(self, host: str, port: int, username: str, password: str, mailbox: str = "INBOX") -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox

    def _connect(self) -> imaplib.IMAP4_SSL:
        client = imaplib.IMAP4_SSL(self.host, self.port)
        client.login(self.username, self.password)
        self._send_imap_id(client)

        # Some providers may reject an explicit mailbox name but accept default select().
        selected = False
        last_error = ""
        for box in (self.mailbox, "INBOX", None):
            try:
                if box is None:
                    status, data = client.select()
                else:
                    status, data = client.select(box)
                if status == "OK":
                    selected = True
                    break
                last_error = str(data)
            except Exception:
                continue

        if not selected:
            client.logout()
            raise RuntimeError(
                f"IMAP login succeeded, but failed to select mailbox. Server response: {last_error}"
            )
        return client

    def _send_imap_id(self, client: imaplib.IMAP4_SSL) -> None:
        # RFC2971: some providers (including NetEase in certain risk states) may require
        # client identification before mailbox selection.
        if os.getenv("IMAP_SEND_ID", "1").strip().lower() in ("0", "false", "no"):
            return

        fields = {
            "name": os.getenv("IMAP_ID_NAME", "netease-mail-agent"),
            "version": os.getenv("IMAP_ID_VERSION", "1.0.0"),
            "vendor": os.getenv("IMAP_ID_VENDOR", "custom"),
            "contact": os.getenv("IMAP_ID_CONTACT", "kefu@188.com"),
        }

        pairs: list[str] = []
        for k, v in fields.items():
            key = str(k).replace('"', "")
            val = str(v).replace('"', "")
            pairs.append(f'"{key}" "{val}"')
        id_payload = "(" + " ".join(pairs) + ")"

        try:
            # imaplib does not expose a public ID helper; use low-level command.
            client._simple_command("ID", id_payload)
        except Exception:
            # Best-effort only: keep compatibility for servers that do not support ID.
            pass

    def fetch_recent(self, lookback_hours: int = 24, fetch_limit: int = 100) -> List[RawMail]:
        now_utc = datetime.now(timezone.utc)
        since_date = (now_utc - timedelta(hours=lookback_hours)).strftime("%d-%b-%Y")

        mails: List[RawMail] = []
        client: Optional[imaplib.IMAP4_SSL] = None
        try:
            client = self._connect()
            status, data = client.search(None, f'(SINCE "{since_date}")')
            if status != "OK" or not data or not data[0]:
                return []

            uids = data[0].split()
            if fetch_limit > 0:
                uids = uids[-fetch_limit:]

            for uid_bytes in reversed(uids):
                uid = uid_bytes.decode("utf-8", errors="ignore")
                f_status, fetched = client.fetch(uid_bytes, "(RFC822)")
                if f_status != "OK" or not fetched:
                    continue

                raw_bytes = fetched[0][1]
                msg = email.message_from_bytes(raw_bytes)
                message_id = (msg.get("Message-ID") or uid).strip()
                date_header = msg.get("Date")
                try:
                    dt = email.utils.parsedate_to_datetime(date_header) if date_header else now_utc
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    dt = now_utc

                if dt < now_utc - timedelta(hours=lookback_hours):
                    continue

                mails.append(
                    RawMail(
                        uid=uid,
                        message_id=message_id,
                        received_at=dt,
                        raw_bytes=raw_bytes,
                    )
                )
            return mails
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
                client.logout()


def decode_mime_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value
