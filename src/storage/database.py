from __future__ import annotations

import json
from pathlib import Path
from typing import Set


class ProcessedStateDB:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_ids(self) -> Set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return set()

        if isinstance(data, dict):
            return {str(k) for k in data.keys()}
        if isinstance(data, list):
            return {str(v) for v in data}
        return set()

    def save_ids(self, message_ids: Set[str]) -> None:
        data = {mid: True for mid in sorted(message_ids)}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
