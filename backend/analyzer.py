"""Claude による1号の分析（記事の範囲指定・要約・国/ジャンル付け）。

analyzer は `analyze(newsletter_name, subject, numbered_text, prior) -> dict` を持つ任意のオブジェクト。
テストでは偽物に差し替える。本文・要約はログに出さない。
"""
from __future__ import annotations

import json

from textutil import GENRES

MODEL = "claude-haiku-5-5"
EFFORT = "medium"
MAX_TOKENS = 32000


class AnalysisError(Exception):
    """分析失敗。メッセージに本文を混ぜない。"""


SCHEMA = {
    "type": "object",
    "properties": {
        "number": {"type": "integer", "description": "号数。分からなければ0"},
        "title": {"type": "string", "description": "号のタイトル。件名や本文冒頭から（例: 今週の動き（1/1～7）架空の島国の選挙）"},
        "headline": {"type": "string", "description": "この号の一言要約。60字以内"},
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "summary": {"type": "string", "description": "3〜4文の要約"},
                    "points": {"type": "array", "items": {"type": "string"}},
                    "countries": {"type": "array", "items": {"type": "string"}},
                    "genres": {"type": "array", "items": {"type": "string", "enum": GENRES}},
                },
                "required": ["title", "start_line", "end_line", "summary", "points", "countries", "genres"],
                "additionalProperties": False,
            },
        },
        "summary": {
            "type": "object",
            "properties": {
                "toc": {"type": "array", "items": {"type": "string"}},
                "points": {"type": "array", "items": {"type": "string"}},
                "changes": {"type": "array", "items": {"type": "string"}},
                "watch_next": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["toc", "points", "changes", "watch_next"],
            "additionalProperties": False,
        },
    },
    "required": ["number", "title", "headline", "articles", "summary"],
    "additionalProperties": False,
}

SYSTEM = """あなたは有料メルマガの読者向け要約アシスタントです。1通のメルマガ本文を読み、構造化して返します。

ルール:
- 本文は各行の先頭に「行番号|」が付いています。記事（話題のまとまり）ごとに、開始行(start_line)と終了行(end_line)を行番号で返してください。本文そのものは返さないでください。記事は本文の並び順に、重ならないように区切ります。原文の見出しや区切りに従い、無理に細かく分けないでください。
- 各記事: title(見出し。原文の見出しがあればそれを使う)、summary(3〜4文)、points(要点を2〜4個)、countries、genres。
- countries は日本語の通称で書く。米国 / 中国 / 日本 / ロシア / ウクライナ / 韓国 / 北朝鮮 / 台湾 / インド / イラン / イスラエル / 英国 / フランス / ドイツ / EU / ブラジル など。「アメリカ」は「米国」。地域だけの話は「中東」「欧州」などでよい。
- genres は指定の選択肢から1〜3個。
- 要約は専門用語を知らない人にも分かるよう、平易な日本語で。本文にない事実を足さない。
- summary.toc: 今回の内容の箇条書き。summary.points: 重要ポイント(専門用語は噛み砕く)。summary.changes: 「前の号から」の変化・進展。参考として渡される過去の号の情報と比べて書き、過去の号が無い、または比べられないときは空配列。summary.watch_next: 次号への注目ポイント1〜2点。
- number は号数（「第123号」なら123）。分からなければ0。headline は60字以内。"""


def build_user_prompt(newsletter_name: str, subject: str, numbered_text: str, prior: list[dict]) -> str:
    parts = [f"誌名: {newsletter_name}", f"件名: {subject}", ""]
    if prior:
        parts.append("【過去の号（古い順、変化の比較用）】")
        for p in prior:
            parts.append(json.dumps(p, ensure_ascii=False))
        parts.append("")
    else:
        parts += ["【過去の号】なし", ""]
    parts += ["【本文（行番号つき）】", numbered_text]
    return "\n".join(parts)


def build_request(newsletter_name: str, subject: str, numbered_text: str, prior: list[dict]) -> dict:
    return dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": build_user_prompt(newsletter_name, subject, numbered_text, prior)}],
    )


class ClaudeAnalyzer:
    def __init__(self, client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から
        self.client = client
        self.last_usage = None

    def analyze(self, newsletter_name: str, subject: str, numbered_text: str, prior: list[dict]) -> dict:
        req = build_request(newsletter_name, subject, numbered_text, prior)
        with self.client.messages.stream(**req) as stream:
            msg = stream.get_final_message()
        self.last_usage = getattr(msg, "usage", None)
        if msg.stop_reason != "end_turn":
            raise AnalysisError(f"stop_reason={msg.stop_reason}")
        text = next((b.text for b in msg.content if b.type == "text"), None)
        if text is None:
            raise AnalysisError("no text block")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise AnalysisError("invalid json") from None  # 本文断片を例外に含めない
