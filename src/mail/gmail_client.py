from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from mail.imap_client import RawMail


class GmailApiClient:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, user_email: str, client_secret_path: str, token_path: str) -> None:
        self.user_email = user_email
        self.client_secret_path = Path(client_secret_path)
        self.token_path = Path(token_path)

    def _get_credentials(self) -> Credentials:
        creds: Credentials | None = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)

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

    def fetch_recent(self, lookback_hours: int = 24, fetch_limit: int = 100) -> List[RawMail]:
        creds = self._get_credentials()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        now_utc = datetime.now(timezone.utc)
        start_utc = now_utc - timedelta(hours=lookback_hours)
        # Gmail search query uses unix seconds for 'after:'.
        query = f"after:{int(start_utc.timestamp())}"

        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=fetch_limit)
            .execute()
        )
        messages = response.get("messages", [])

        result: List[RawMail] = []
        for item in messages:
            gmail_id = item.get("id")
            if not gmail_id:
                continue

            msg = (
                service.users()
                .messages()
                .get(userId="me", id=gmail_id, format="raw")
                .execute()
            )
            raw_encoded = msg.get("raw", "")
            if not raw_encoded:
                continue

            padding = "=" * (-len(raw_encoded) % 4)
            raw_bytes = base64.urlsafe_b64decode(raw_encoded + padding)

            internal_ms = int(msg.get("internalDate", "0"))
            received_at = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc) if internal_ms else now_utc
            if received_at < start_utc:
                continue

            result.append(
                RawMail(
                    uid=gmail_id,
                    message_id=gmail_id,
                    received_at=received_at,
                    raw_bytes=raw_bytes,
                )
            )

        return result
