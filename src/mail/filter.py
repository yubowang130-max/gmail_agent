from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from mail.parser import ParsedMail


@dataclass
class MailFilterRules:
    include_senders: list[str]
    exclude_senders: list[str]
    include_subject_keywords: list[str]
    exclude_subject_keywords: list[str]
    priority_subject_keywords: list[str]
    ad_ai_keywords: list[str]
    sales_keywords: list[str]


def _contains_any(text: str, patterns: Iterable[str]) -> bool:
    t = text.lower()
    return any(p.lower() in t for p in patterns if p)


def filter_mails(mails: list[ParsedMail], rules: MailFilterRules) -> List[ParsedMail]:
    result: List[ParsedMail] = []

    for mail in mails:
        sender = mail.sender_email.lower()
        subject = mail.subject.lower()

        if rules.include_senders and not _contains_any(sender, rules.include_senders):
            continue
        if rules.exclude_senders and _contains_any(sender, rules.exclude_senders):
            continue
        if rules.include_subject_keywords and not _contains_any(subject, rules.include_subject_keywords):
            continue
        if rules.exclude_subject_keywords and _contains_any(subject, rules.exclude_subject_keywords):
            continue
        if is_sales_mail(mail, rules):
            continue

        result.append(mail)

    return result


def is_priority_mail(mail: ParsedMail, rules: MailFilterRules) -> bool:
    if not rules.priority_subject_keywords:
        return False
    return _contains_any(mail.subject, rules.priority_subject_keywords)


def is_ai_related_mail(mail: ParsedMail, rules: MailFilterRules) -> bool:
    if not rules.ad_ai_keywords:
        return False
    text = f"{mail.subject} {mail.body_preview}"
    return _contains_any(text, rules.ad_ai_keywords)


def is_sales_mail(mail: ParsedMail, rules: MailFilterRules) -> bool:
    if not rules.sales_keywords:
        return False
    text = f"{mail.subject} {mail.body_preview}"
    return _contains_any(text, rules.sales_keywords)
