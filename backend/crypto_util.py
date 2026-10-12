"""AES-256-GCM 暗号化ユーティリティ。

形式: base64( nonce(12) || ciphertext || tag(16) )、AADなし。
Swift CryptoKit の AES.GCM.SealedBox(combined:) がそのまま読める。
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent.parent


def load_key() -> bytes:
    """DATA_KEY 環境変数、なければ .secrets/data_key.b64 から32バイト鍵を読む。"""
    raw = os.environ.get("DATA_KEY", "").strip()
    if not raw:
        p = ROOT / ".secrets" / "data_key.b64"
        if p.exists():
            raw = p.read_text().strip()
    if not raw:
        raise RuntimeError("DATA_KEY not found (env DATA_KEY or .secrets/data_key.b64)")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("DATA_KEY must decode to 32 bytes")
    return key


def encrypt_bytes(plain: bytes, key: bytes) -> str:
    nonce = os.urandom(12)
    sealed = AESGCM(key).encrypt(nonce, plain, None)  # ciphertext || tag
    return base64.b64encode(nonce + sealed).decode("ascii")


def decrypt_bytes(b64text: str, key: bytes) -> bytes:
    blob = base64.b64decode(b64text.strip())
    if len(blob) < 12 + 16:
        raise ValueError("ciphertext too short")
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


def encrypt_json(obj: Any, key: bytes) -> str:
    return encrypt_bytes(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), key)


def decrypt_json(b64text: str, key: bytes) -> Any:
    return json.loads(decrypt_bytes(b64text, key).decode("utf-8"))


def write_enc(path: Path, obj: Any, key: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(encrypt_json(obj, key))
    tmp.replace(path)


def read_enc(path: Path, key: bytes) -> Any:
    return decrypt_json(path.read_text(), key)
