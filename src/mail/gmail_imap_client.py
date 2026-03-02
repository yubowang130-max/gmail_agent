from __future__ import annotations

from datetime import datetime, timedelta, timezone
import email
import imaplib
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from mail.imap_client import RawMail


class GmailImapOAuthClient:
    SCOPES = ["https://mail.google.com/"]

    def __init__(
        self,
        user_email: str,
        client_secret_path: str,
        token_path: str,
        host: str = "imap.gmail.com",
        port: int = 993,
        mailbox: str = "INBOX",
    ) -> None:
        self.user_email = user_email
        self.client_secret_path = Path(client_secret_path)
        self.token_path = Path(token_path)
        self.host = host
        self.port = port
        self.mailbox = mailbox

    def _get_credentials(self, force_reauth: bool = False) -> Credentials:
        creds: Credentials | None = None
        if self.token_path.exists() and not force_reauth:
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
            if creds and not creds.has_scopes(self.SCOPES):
                creds = None

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _connect(self) -> imaplib.IMAP4_SSL:
        def _auth_with_token(creds: Credentials) -> imaplib.IMAP4_SSL:
            if not creds.token:
                raise RuntimeError("Gmail OAuth token is empty.")
            c = imaplib.IMAP4_SSL(self.host, self.port)
            auth_string = f"user={self.user_email}\x01auth=Bearer {creds.token}\x01\x01"
            c.authenticate("XOAUTH2", lambda _: auth_string.encode("utf-8"))
            status, data = c.select(self.mailbox)
            if status != "OK":
                c.logout()
                raise RuntimeError(f"Gmail IMAP select failed: {data}")
            return c

        try:
            return _auth_with_token(self._get_credentials())
        except imaplib.IMAP4.error:
            # Token may be stale or revoked; force OAuth re-consent once.
            if self.token_path.exists():
                self.token_path.unlink(missing_ok=True)
            return _auth_with_token(self._get_credentials(force_reauth=True))

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
