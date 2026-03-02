from __future__ import annotations

from datetime import datetime
from typing import List

from mail.filter import MailFilterRules, is_ai_related_mail, is_priority_mail
from mail.parser import ParsedMail


def build_summary_prompt(mails: List[ParsedMail], rules: MailFilterRules) -> str:
    lines: list[str] = []
    for i, mail in enumerate(mails, start=1):
        priority_flag = "[PRIORITY]" if is_priority_mail(mail, rules) else "[NORMAL]"
        ad_flag = "[AD_AI]" if is_ai_related_mail(mail, rules) else "[NON_AD_AI]"
        lines.extend(
            [
                f"{i}. {priority_flag} {ad_flag}",
                f"Sender: {mail.sender_name} <{mail.sender_email}>",
                f"Subject: {mail.subject}",
                f"Time: {mail.date_iso}",
                f"Body Preview: {mail.body_preview}",
                "",
            ]
        )

    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
You are an email analyst assistant. Summarize the daily inbox into Chinese.

Rules:
1) Output concise markdown.
2) Start with title: Gmail每日总结.
3) Include total count.
4) Split output into exactly two sections:
   - 核心邮件（工作/通知/待办）
   - 广告与资讯（仅保留编程或AI相关内容）
5) Do not include sales-style ads (discount, coupon, promotion, limited-time sale, buy-now style).
6) Add section 待处理事项 with actionable bullet points.
7) End with 自动生成时间: {today}

Emails:
{chr(10).join(lines)}
""".strip()
