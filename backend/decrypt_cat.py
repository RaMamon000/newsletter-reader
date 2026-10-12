#!/usr/bin/env python3
"""ローカル確認用: .enc を復号して JSON を表示する（Actionsでは使わない）。

使い方: python backend/decrypt_cat.py data/index.json.enc
        python backend/decrypt_cat.py data/issues/xxxx.json.enc --keys   # 項目名だけ
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_util import load_key, read_enc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--keys", action="store_true", help="トップレベルの項目名と長さだけ表示")
    a = ap.parse_args()
    obj = read_enc(Path(a.path), load_key())
    if a.keys and isinstance(obj, dict):
        for k, v in obj.items():
            print(k, type(v).__name__, len(v) if hasattr(v, "__len__") else v)
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
