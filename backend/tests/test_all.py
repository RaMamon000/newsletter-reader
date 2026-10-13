import base64
import json
import os
from datetime import datetime, timezone

import pytest

import analyzer as an
import apns
import crypto_util as cu
import gmail_source as gs
import pipeline as pl
from textutil import normalize_countries, normalize_genres, strip_footer

KEY = os.urandom(32)

BODY1 = """第123号 ペルー大統領選
今週の動き

■1 ペルー大統領選
決選投票が行われた。候補X氏が勝利。
アメリカとの関係が焦点。

■2 ウクライナ情勢
停戦協議が続く。ロシアは強硬姿勢。

--------------------
配信停止はこちら
https://example.invalid/unsub
"""
BODY2 = "第901号 テスト\n\n■1 日本の政局\n国会が開会した。\n\n■2 中国経済\n成長率が鈍化。\n"


def ms(y, m, d):
    return int(datetime(y, m, d, 7, tzinfo=timezone.utc).timestamp() * 1000)


class FakeSource:
    def __init__(self):
        self.msgs = {
            "aaaaaaaa11": {"subject": "【テスト誌A】第123号", "date_ms": ms(2026, 10, 5), "text": BODY1},
            "bbbbbbbb22": {"subject": "【テスト誌B】第12号", "date_ms": ms(2026, 10, 6), "text": BODY2},
            "cccccccc33": {"subject": "【テスト誌A】第901号", "date_ms": ms(2026, 10, 12), "text": BODY2},
            "dddddddd44": {"subject": "関係ないお知らせ", "date_ms": ms(2026, 10, 7), "text": "x"},
        }

    def list_ids(self, all_pages):
        return list(self.msgs)  # 新しい順とは限らない

    def get_meta(self, mid):
        m = self.msgs[mid]
        return {"subject": m["subject"], "date_ms": m["date_ms"]}

    def get_message(self, mid):
        return dict(self.msgs[mid])


class FakeAnalyzer:
    def __init__(self):
        self.calls = []

    def analyze(self, name, subject, numbered, prior):
        self.calls.append(prior)
        n = len(numbered.split("\n"))
        # 本文を 2 記事に割る（1行目ヘッダを除く）
        mid = next((i for i, l in enumerate(numbered.split("\n")) if "■2" in l), n)
        return {
            "number": 123, "title": "今週の動き ペルー大統領選", "headline": "あ" * 80,
            "articles": [
                {"title": "A", "start_line": 3, "end_line": mid - 1, "summary": "s", "points": ["p"],
                 "countries": ["アメリカ", "ペルー"], "genres": ["選挙", "謎ジャンル"]},
                {"title": "B", "start_line": mid, "end_line": n, "summary": "s", "points": ["p"],
                 "countries": ["ロシア連邦"], "genres": ["戦争・紛争"]},
            ],
            "summary": {"toc": ["a"], "points": ["b"], "changes": [], "watch_next": ["c"]},
        }


def test_crypto_roundtrip_and_format():
    obj = {"a": "日本語", "b": [1, 2]}
    enc = cu.encrypt_json(obj, KEY)
    raw = base64.b64decode(enc)
    assert len(raw) == 12 + len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()) + 16
    assert cu.decrypt_json(enc, KEY) == obj
    assert cu.encrypt_json(obj, KEY) != enc  # nonce は毎回違う
    with pytest.raises(Exception):
        cu.decrypt_json(enc, os.urandom(32))


def test_load_key_from_secrets_file_valid():
    k = cu.load_key()  # .secrets/data_key.b64 or env
    assert len(k) == 32


def test_footer_and_normalize():
    t = strip_footer(BODY1)
    assert "配信停止" not in t and t.endswith("アメリカとの関係が焦点。\n\n■2 ウクライナ情勢\n停戦協議が続く。ロシアは強硬姿勢。".rstrip()) 
    assert strip_footer(BODY2) == BODY2.strip("\n")
    assert normalize_countries(["アメリカ", "米", "ペルー"]) == ["米国", "ペルー"]
    assert normalize_genres(["選挙", "ほげ", "x", "y"]) == ["選挙", "その他"]
    # 本文の途中に「配信停止」が出ても先頭側は削らない
    mid = "配信停止の話題\n" + "行\n" * 100
    assert strip_footer(mid).startswith("配信停止の話題")


def test_cut_articles_is_verbatim_and_robust():
    lines = ["a", "b", "", "---", "c", "d"]
    arts = pl.cut_articles(lines, [
        {"title": "x", "start_line": 1, "end_line": 2}, {"title": "y", "start_line": 5, "end_line": 99}])
    assert arts[0]["body"] == "a\nb\n\n---"  # 隙間の区切りは前の記事に含める
    assert arts[1]["body"] == "c\nd"
    assert pl.cut_articles(lines, [])[0]["body"] == "a\nb\n\n---\nc\nd"  # 全滅なら全文1記事
    overlap = pl.cut_articles(lines, [{"title": "x", "start_line": 1, "end_line": 4}, {"title": "y", "start_line": 3, "end_line": 6}])
    assert [a["idx"] for a in overlap] == [0, 1] and overlap[1]["body"] == "c\nd"


def test_pipeline_end_to_end(tmp_path, capsys):
    pushed = []
    fa = FakeAnalyzer()
    r = pl.run(FakeSource(), fa, tmp_path, KEY, push=pushed.append)
    out = capsys.readouterr().out
    assert r["processed"] == 3 and r["failed"] == 0
    # ログに本文・件名が出ていない
    for leak in ("ペルー", "候補X", "テスト誌A", "テスト誌B", "停戦", "関係ない"):
        assert leak not in out, leak
    idx = cu.read_enc(tmp_path / "index.json.enc", KEY)
    assert [i["date"] for i in idx["issues"]] == sorted([i["date"] for i in idx["issues"]], reverse=True)
    assert idx["issues"][0]["id"] == "nl1-20261012-cccccccc33"
    first = next(i for i in idx["issues"] if i["id"] == "nl1-20261005-aaaaaaaa11")
    assert len(first["headline"]) == 60
    assert first["articles"][0]["countries"] == ["米国", "ペルー"]
    assert first["articles"][0]["genres"] == ["選挙", "その他"]
    issue = cu.read_enc(tmp_path / "issues" / "nl1-20261005-aaaaaaaa11.json.enc", KEY)
    assert "配信停止" not in issue["full_text"]
    for a in issue["articles"]:
        assert a["body"] in issue["full_text"]  # 原文の切り出し
    assert issue["gmail_link"].endswith("#all/aaaaaaaa11")
    assert "ペルー" not in (tmp_path / "index.json.enc").read_text()  # 平文が出ていない
    # 古い順に処理され、2号目の nl1 は前の号を参照している
    assert fa.calls[0] == [] and any(c for c in fa.calls)
    assert any(len(p) == 1 and p[0]["number"] == 123 for p in fa.calls)
    assert len(pushed) == 3
    # 2回目は何もしない（state）
    fa2 = FakeAnalyzer()
    r2 = pl.run(FakeSource(), fa2, tmp_path, KEY, push=pushed.append)
    assert r2["processed"] == 0 and fa2.calls == [] and len(pushed) == 3


def test_limit_dry_run_and_failure(tmp_path, capsys):
    fa = FakeAnalyzer()
    r = pl.run(FakeSource(), fa, tmp_path / "d", KEY, dry_run=True)
    assert r["processed"] == 3 and fa.calls == [] and not (tmp_path / "d").exists()
    r = pl.run(FakeSource(), fa, tmp_path / "l", KEY, limit=1, backfill=True)
    assert r["processed"] == 1
    assert list((tmp_path / "l" / "issues").glob("*.enc"))[0].name.startswith("nl1-20261005")

    class Boom:
        def analyze(self, *a):
            raise an.AnalysisError("本文ペルー")
    capsys.readouterr()
    r = pl.run(FakeSource(), Boom(), tmp_path / "f", KEY)
    out = capsys.readouterr().out
    assert r["failed"] == 3 and "ペルー" not in out and "AnalysisError" in out
    st = cu.read_enc(tmp_path / "f" / "state.json.enc", KEY)
    assert st["processed"] == {}  # 失敗した号は次回また試す


def test_claude_request_shape_and_parse():
    req = an.build_request("誌", "件名", "1|本文", [])
    assert req["model"] == "claude-haiku-5-5"
    assert req["output_config"]["effort"] == "medium"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in req and "thinking" not in req and "tool_choice" not in req

    class Msg:
        stop_reason = "end_turn"
        usage = None
        content = [type("B", (), {"type": "text", "text": json.dumps({"number": 1})})()]

    class Stream:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get_final_message(self): return Msg()

    class Client:
        class messages:
            @staticmethod
            def stream(**kw):
                assert kw["model"] == "claude-haiku-5-5"
                return Stream()
    assert an.ClaudeAnalyzer(Client()).analyze("誌", "件名", "1|x", []) == {"number": 1}
    Msg.stop_reason = "refusal"
    with pytest.raises(an.AnalysisError):
        an.ClaudeAnalyzer(Client()).analyze("誌", "件名", "1|x", [])


def test_gmail_body_extraction():
    def b(s): return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": b("<p>HTML版</p>")}},
        {"mimeType": "text/plain", "body": {"data": b("プレーン版\r\n二行目")}}]}
    assert gs.extract_body(payload) == "プレーン版\n二行目"
    payload["parts"].pop(1)
    assert "HTML版" in gs.extract_body(payload)


def test_apns_jwt_and_payload():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    import jwt
    k = ec.generate_private_key(ec.SECP256R1())
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption()).decode()
    cfg = apns.ApnsConfig(pem.replace("\n", "\\n"), "KEYID12345", "TEAMID1234", "tok")
    t = jwt.decode(apns.make_jwt(cfg, 1000), k.public_key(), algorithms=["ES256"], options={"verify_iat": False})
    assert t == {"iss": "TEAMID1234", "iat": 1000}
    assert jwt.get_unverified_header(apns.make_jwt(cfg))["kid"] == "KEYID12345"
    p = apns.build_payload("誌", "本", "id1")
    assert p["issue_id"] == "id1" and p["aps"]["alert"]["title"] == "誌"


def test_issue_ids_do_not_collide_on_same_day():
    # 同じ日に続けて届いたメールは番号の先頭8文字が重なる（2026-01-15 に3通で実際に起きた）
    a = pl.make_issue_id("nl2", ms(2026, 1, 15), "19bbefb6c886c5e3")
    b = pl.make_issue_id("nl2", ms(2026, 1, 15), "19bbefb6cbe397a8")
    assert a != b


def test_inbox_eml_is_processed_like_gmail(tmp_path):
    import inbox
    raw = ("From: x <a@example.invalid>\r\nSubject: =?UTF-8?B?" + base64.b64encode("【テスト誌A】第5号".encode()).decode()
           + "?=\r\nDate: Tue, 13 Oct 2026 07:10:00 +0900\r\nMIME-Version: 1.0\r\n"
           "Content-Type: text/html; charset=utf-8\r\n\r\n<h2>見出し</h2><p>本文です</p>\r\n").encode()
    msg = inbox.parse_eml(raw)
    assert msg["subject"] == "【テスト誌A】第5号" and "見出し\n" in msg["text"] and "本文です" in msg["text"]
    mid = inbox.eml_id(raw)
    cu.write_enc(tmp_path / "inbox" / f"{mid}.json.enc", msg, KEY)

    class Empty:
        def list_ids(self, all_pages): return []
    src = inbox.InboxSource(Empty(), tmp_path / "inbox", KEY)
    assert src.list_ids(False) == [mid]
    res = pl.run(src, FakeAnalyzer(), tmp_path, KEY)
    assert res["processed"] == 1
    issue = res["new_issues"][0]
    assert issue["id"].endswith(mid) and issue["gmail_link"] == ""
    assert pl.run(src, FakeAnalyzer(), tmp_path, KEY)["processed"] == 0  # 2回目は処理しない
