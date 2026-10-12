"""Gmail からの取得と本文の取り出し。

Source のインターフェース（テストでは偽物に差し替える）:
  list_ids(all_pages: bool) -> list[str]
  get_meta(mid) -> {"subject": str, "date_ms": int}
  get_message(mid) -> {"subject": str, "date_ms": int, "text": str}   # フッター除去前の本文
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
from nlconfig import QUERY  # noqa: E402  差出人は秘密の設定から
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def load_token_info() -> dict | None:
    raw = os.environ.get("GMAIL_TOKEN_JSON", "").strip()
    if raw:
        return json.loads(raw)
    p = ROOT / ".secrets" / "gmail_token.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def _b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    charset = "utf-8"
    for h in part.get("headers", []):
        if h["name"].lower() == "content-type":
            m = re.search(r'charset="?([\w\-]+)', h["value"], re.I)
            if m:
                charset = m.group(1)
    try:
        return _b64(data).decode(charset, errors="replace")
    except LookupError:
        return _b64(data).decode("utf-8", errors="replace")


def _walk(part: dict):
    yield part
    for sub in part.get("parts", []) or []:
        yield from _walk(sub)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4"]):
        p.append("\n")
    return soup.get_text()


def extract_body(payload: dict) -> str:
    """text/plain を優先、なければ HTML をテキスト化。"""
    plain, html = [], []
    for p in _walk(payload):
        mt = p.get("mimeType", "")
        if mt == "text/plain":
            plain.append(_decode_part(p))
        elif mt == "text/html":
            html.append(_decode_part(p))
    text = "\n".join(x for x in plain if x.strip())
    if not text.strip() and html:
        text = html_to_text("\n".join(html))
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


class GmailSource:
    def __init__(self, token_info: dict, service=None):
        if service is None:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self.svc = service.users().messages()

    def list_ids(self, all_pages: bool) -> list[str]:
        ids, token = [], None
        while True:
            r = self.svc.list(userId="me", q=QUERY, maxResults=100, pageToken=token).execute()
            ids += [m["id"] for m in r.get("messages", [])]
            token = r.get("nextPageToken")
            if not all_pages or not token:
                return ids

    def get_meta(self, mid: str) -> dict:
        m = self.svc.get(userId="me", id=mid, format="metadata", metadataHeaders=["Subject"]).execute()
        return {"subject": _header(m["payload"], "Subject"), "date_ms": int(m["internalDate"])}

    def get_message(self, mid: str) -> dict:
        m = self.svc.get(userId="me", id=mid, format="full").execute()
        return {"subject": _header(m["payload"], "Subject"), "date_ms": int(m["internalDate"]),
                "text": extract_body(m["payload"])}
