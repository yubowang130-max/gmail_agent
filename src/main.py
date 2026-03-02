from __future__ import annotations

import argparse
from datetime import datetime, date
import logging
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
import yaml

from llm.summarizer import MailSummarizer
from mail.filter import MailFilterRules, filter_mails
from mail.gmail_client import GmailApiClient
from mail.imap_client import NeteaseImapClient
from mail.parser import parse_raw_mail
from notify.feishu import FeishuNotifier
from storage.database import ProcessedStateDB


def setup_logging(project_root: Path) -> None:
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daily.log"

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def print_safe(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def load_rules(path: Path) -> MailFilterRules:
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    return MailFilterRules(
        include_senders=raw.get("include_senders", []) or [],
        exclude_senders=raw.get("exclude_senders", []) or [],
        include_subject_keywords=raw.get("include_subject_keywords", []) or [],
        exclude_subject_keywords=raw.get("exclude_subject_keywords", []) or [],
        priority_subject_keywords=raw.get("priority_subject_keywords", []) or [],
        ad_ai_keywords=raw.get("ad_ai_keywords", []) or [],
        sales_keywords=raw.get("sales_keywords", []) or [],
    )


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required env: {name}")
    return value


def run(
    dry_run: bool = False,
    lookback_hours_override: int | None = None,
    target_date: date | None = None,
    ignore_state: bool = False,
) -> None:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    setup_logging(project_root)

    rules = load_rules(project_root / "config" / "rules.yaml")

    mail_provider = os.getenv("MAIL_PROVIDER", "imap").strip().lower()
    mail_user = require_env("MAIL_USER")
    lookback_hours = (
        lookback_hours_override if lookback_hours_override is not None else int(os.getenv("MAIL_LOOKBACK_HOURS", "24"))
    )
    fetch_limit = int(os.getenv("MAIL_FETCH_LIMIT", "100"))

    db = ProcessedStateDB(str(project_root / "src" / "storage" / "state.json"))
    processed_ids = set() if ignore_state else db.load_ids()

    if mail_provider == "gmail":
        client_secret_path = os.getenv("GMAIL_CLIENT_SECRET_PATH", str(project_root / "client_secret.json"))
        token_path = os.getenv("GMAIL_TOKEN_PATH", str(project_root / "gmail_token.json"))
        client = GmailApiClient(
            user_email=mail_user,
            client_secret_path=client_secret_path,
            token_path=token_path,
        )
    else:
        mail_pass = require_env("MAIL_PASS")
        imap_host = os.getenv("IMAP_HOST", "imap.163.com")
        imap_port = int(os.getenv("IMAP_PORT", "993"))
        client = NeteaseImapClient(imap_host, imap_port, mail_user, mail_pass)

    raw_mails = client.fetch_recent(lookback_hours=lookback_hours, fetch_limit=fetch_limit)
    logging.info("Fetched %s raw emails.", len(raw_mails))

    parsed = [parse_raw_mail(m, max_preview_chars=500) for m in raw_mails]
    if target_date is not None:
        parsed = [
            m
            for m in parsed
            if datetime.fromisoformat(m.date_iso).astimezone().date() == target_date
        ]
        logging.info("After date filter (%s): %s emails.", target_date.isoformat(), len(parsed))

    parsed = [m for m in parsed if m.message_id not in processed_ids]
    filtered = filter_mails(parsed, rules)
    logging.info("After dedupe+filter: %s emails.", len(filtered))

    summarizer = MailSummarizer()
    report = summarizer.summarize(filtered, rules)

    title_prefix = "Gmail每日总结" if mail_provider == "gmail" else "网易邮箱每日总结"
    header_date = f"\n统计日期：{target_date.isoformat()}" if target_date is not None else ""
    report_header = f"{title_prefix}{header_date}\n自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    final_text = report_header + report

    if dry_run:
        logging.info("Dry-run enabled, skip Feishu send.")
        print_safe(final_text)
    else:
        notifier = FeishuNotifier()
        notifier.send_markdown("今日邮件总结", final_text)
        logging.info("Feishu push sent.")

    if filtered and not ignore_state:
        new_ids = {m.message_id for m in filtered}
        processed_ids.update(new_ids)
        db.save_ids(processed_ids)
        logging.info("Saved %s processed IDs.", len(processed_ids))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Netease Mail Daily Report Agent")
    parser.add_argument("--dry-run", action="store_true", help="Generate report without Feishu sending")
    parser.add_argument("--lookback-hours", type=int, default=None, help="Override mail lookback hours")
    parser.add_argument("--target-date", type=str, default=None, help="Only summarize this local date (YYYY-MM-DD)")
    parser.add_argument("--ignore-state", action="store_true", help="Ignore processed state.json for one-off report")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_date = datetime.strptime(args.target_date, "%Y-%m-%d").date() if args.target_date else None
    run(
        dry_run=args.dry_run,
        lookback_hours_override=args.lookback_hours,
        target_date=target_date,
        ignore_state=args.ignore_state,
    )
