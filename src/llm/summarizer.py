from __future__ import annotations

import json
import os
from typing import List

import requests
from openai import OpenAI

from llm.prompt import build_summary_prompt
from mail.filter import MailFilterRules
from mail.parser import ParsedMail


class MailSummarizer:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def summarize(self, mails: List[ParsedMail], rules: MailFilterRules) -> str:
        if not mails:
            return (
                "# Gmail每日总结\n\n"
                "今日共收到：0 封有效邮件\n\n"
                "## 核心邮件\n- 无\n\n"
                "## 广告与资讯（编程/AI）\n- 无\n\n"
                "## 待处理事项\n- 无\n"
            )

        prompt = build_summary_prompt(mails, rules)

        if self.provider == "ollama":
            return self._summarize_ollama(prompt)
        return self._summarize_openai_compatible(prompt)

    def _summarize_openai_compatible(self, prompt: str) -> str:
        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
        if not api_key:
            raise ValueError("LLM_API_KEY is required for openai-compatible provider")

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You create concise Chinese email summaries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

    def _summarize_ollama(self, prompt: str) -> str:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        r = requests.post(f"{base_url}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        text = data.get("response", "").strip()
        if not text:
            raise RuntimeError(f"Ollama empty response: {json.dumps(data, ensure_ascii=False)}")
        return text
