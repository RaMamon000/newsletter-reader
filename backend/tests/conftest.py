import json
import os
import sys
from pathlib import Path

# 本物の差出人・誌名は秘密の設定にあるので、テストでは作り物を使う
os.environ["NEWSLETTER_CONFIG"] = json.dumps({
    "query": "from:sender@example.invalid",
    "newsletters": {"nl1": ["テスト誌A", "テスト誌A（正式名）"], "nl2": ["テスト誌B", "テスト誌B"]},
}, ensure_ascii=False)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
