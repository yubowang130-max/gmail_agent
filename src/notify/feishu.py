from __future__ import annotations

import os

import requests


class FeishuNotifier:
    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK", "")
        if not self.webhook_url:
            raise ValueError("FEISHU_WEBHOOK is required")

    def send_markdown(self, title: str, text: str) -> None:
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [[{"tag": "text", "text": text}]],
                    }
                }
            },
        }
        resp = requests.post(self.webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("StatusCode") not in (0, "0", None):
            raise RuntimeError(f"Feishu API error: {data}")
