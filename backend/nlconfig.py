"""監視対象（差出人・誌名）の設定。公開リポに書かないため、秘密の設定から読む。

環境変数 NEWSLETTER_CONFIG（JSON 文字列）、無ければ .secrets/newsletter_config.json。
形式: {"query": "from:...", "account": "Gmailアドレス", "newsletters": {"nl1": ["件名に含まれる語", "表示名"], ...}}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / ".secrets" / "newsletter_config.json"


def load() -> dict:
    raw = os.environ.get("NEWSLETTER_CONFIG")
    if raw:
        return json.loads(raw)
    if _PATH.exists():
        return json.loads(_PATH.read_text(encoding="utf-8"))
    return {"query": "", "newsletters": {}}


CONFIG = load()
QUERY: str = CONFIG.get("query", "")
NEWSLETTERS: dict[str, tuple[str, str]] = {k: (v[0], v[1]) for k, v in CONFIG.get("newsletters", {}).items()}
ACCOUNT: str = CONFIG.get("account", "")
