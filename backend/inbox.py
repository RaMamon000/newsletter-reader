#!/usr/bin/env python3
"""Gmail に届かなかった号（別のアカウントに届いた .eml など）を手で足すための受け箱。

  python backend/inbox.py <file.eml> ...   → data/inbox/eml-<hash>.json.enc を作る（暗号化済み）

受け箱のファイルは commit すると次の見張りで Gmail の号と同じ流れで処理される。
号IDは eml-<hash> を Gmail の番号の代わりに使う。ログに件名・本文は出さない。
"""
from __future__ import annotations

import email
import hashlib
import sys
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crypto_util  # noqa: E402
from gmail_source import html_to_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "eml-"


def parse_eml(raw: bytes) -> dict:
    """Gmail の get_message と同じ形 {"subject","date_ms","text"} にする。"""
    m = email.message_from_bytes(raw, policy=policy.default)
    plain = m.get_body(("plain",))
    if plain is not None and plain.get_content().strip():
        text = plain.get_content()
    else:
        html = m.get_body(("html",))
        text = html_to_text(html.get_content()) if html is not None else ""
    date_ms = int(parsedate_to_datetime(m["Date"]).timestamp() * 1000)
    return {"subject": str(m["Subject"] or ""), "date_ms": date_ms,
            "text": text.replace("\r\n", "\n").replace("\r", "\n")}


def eml_id(raw: bytes) -> str:
    return PREFIX + hashlib.sha256(raw).hexdigest()[:16]


class InboxSource:
    """Gmail の Source に受け箱の号を足す。受け箱の号は messageId の代わりに eml-<hash>。"""

    def __init__(self, base, inbox_dir: Path, key_bytes: bytes):
        self.base, self.dir, self.key = base, Path(inbox_dir), key_bytes

    def _inbox_ids(self) -> list[str]:
        if not self.dir.exists():
            return []
        return sorted(p.name.removesuffix(".json.enc") for p in self.dir.glob(PREFIX + "*.json.enc"))

    def list_ids(self, all_pages: bool) -> list[str]:
        return self.base.list_ids(all_pages) + self._inbox_ids()

    def _read(self, mid: str) -> dict:
        return crypto_util.read_enc(self.dir / f"{mid}.json.enc", self.key)

    def get_meta(self, mid: str) -> dict:
        if mid.startswith(PREFIX):
            m = self._read(mid)
            return {"subject": m["subject"], "date_ms": m["date_ms"]}
        return self.base.get_meta(mid)

    def get_message(self, mid: str) -> dict:
        return self._read(mid) if mid.startswith(PREFIX) else self.base.get_message(mid)


def main(argv=None) -> int:
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        print("usage: inbox.py <file.eml> ...")
        return 2
    key = crypto_util.load_key()
    out_dir = ROOT / "data" / "inbox"
    for p in paths:
        raw = Path(p).read_bytes()
        msg = parse_eml(raw)
        mid = eml_id(raw)
        crypto_util.write_enc(out_dir / f"{mid}.json.enc", msg, key)
        print(f"added {mid} chars={len(msg['text'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
