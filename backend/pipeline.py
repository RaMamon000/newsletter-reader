#!/usr/bin/env python3
"""メルマガ取得 → 分析 → 暗号化保存 → 通知。

ログ安全: print は件数・号ID・messageId・HTTPステータス・例外の型名だけ。件名・本文・要約は出さない。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crypto_util  # noqa: E402
from textutil import normalize_countries, normalize_genres, strip_footer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

from nlconfig import ACCOUNT, NEWSLETTERS  # noqa: E402  差出人・誌名・アカウントは秘密の設定から


def log(msg: str) -> None:
    print(msg, flush=True)


def safe_err(e: BaseException) -> str:
    """例外を型名とステータスだけに潰す（メッセージに本文が混ざりうるため出さない）。"""
    status = getattr(e, "status_code", None)
    if status is None:
        resp = getattr(e, "resp", None)
        status = getattr(resp, "status", None)
    return type(e).__name__ + (f" status={status}" if status else "")


def classify(subject: str) -> str | None:
    for key, (needle, _) in NEWSLETTERS.items():
        if needle in subject:
            return key
    return None


def make_issue_id(key: str, date_ms: int, mid: str) -> str:
    d = datetime.fromtimestamp(date_ms / 1000, JST).strftime("%Y%m%d")
    return f"{key}-{d}-{mid}"  # 同じ日に続けて届くと先頭8文字が重なるので、番号は全部使う


def number_lines(text: str) -> tuple[list[str], str]:
    lines = text.split("\n")
    return lines, "\n".join(f"{i + 1}|{ln}" for i, ln in enumerate(lines))


_DECOR = re.compile(r"^[\s\-=_*━─―＝■□◆◇▼▽●○・.]*$")


def cut_articles(lines: list[str], raw_articles: list[dict]) -> list[dict]:
    """モデルが返した開始/終了行から、原文をそのまま切り出す。壊れた指定は補正し、全滅なら全文1記事。"""
    n = len(lines)
    spans = []
    for a in raw_articles or []:
        try:
            s, e = int(a["start_line"]), int(a["end_line"])
        except (KeyError, TypeError, ValueError):
            continue
        s, e = max(1, min(s, n)), max(1, min(e, n))
        if e < s:
            s, e = e, s
        spans.append([s, e, a])
    spans.sort(key=lambda x: x[0])
    fixed = []
    prev_end = 0
    for s, e, a in spans:
        s = max(s, prev_end + 1)
        if s > e:
            continue
        fixed.append([s, e, a])
        prev_end = e
    # 次の記事までの隙間が空行・区切り線だけなら前の記事に含める
    for i in range(len(fixed) - 1):
        gap = lines[fixed[i][1]:fixed[i + 1][0] - 1]
        if all(_DECOR.match(g) for g in gap):
            fixed[i][1] = fixed[i + 1][0] - 1
    if not fixed:
        return [{"idx": 0, "title": (raw_articles[0].get("title") if raw_articles else "") or "全文",
                 "body": "\n".join(lines).strip("\n"), "summary": (raw_articles[0].get("summary", "") if raw_articles else ""),
                 "points": (raw_articles[0].get("points", []) if raw_articles else []),
                 "countries": normalize_countries(raw_articles[0].get("countries") if raw_articles else []),
                 "genres": normalize_genres(raw_articles[0].get("genres") if raw_articles else [])}]
    out = []
    for idx, (s, e, a) in enumerate(fixed):
        out.append({
            "idx": idx,
            "title": a.get("title", ""),
            "body": "\n".join(lines[s - 1:e]).strip("\n"),
            "summary": a.get("summary", ""),
            "points": list(a.get("points", [])),
            "countries": normalize_countries(a.get("countries")),
            "genres": normalize_genres(a.get("genres")),
        })
    return out


def build_issue(key: str, mid: str, msg: dict, analysis: dict) -> dict:
    full_text = msg["text"]  # フッター除去済みを渡すこと（分析に渡した本文と同一）
    lines, _ = number_lines(full_text)
    articles = cut_articles(lines, analysis.get("articles", []))
    s = analysis.get("summary", {})
    return {
        "id": make_issue_id(key, msg["date_ms"], mid),
        "newsletter": key,
        "newsletter_name": NEWSLETTERS[key][1],
        "number": analysis.get("number") or None,
        "title": analysis.get("title", ""),
        "date": datetime.fromtimestamp(msg["date_ms"] / 1000, JST).isoformat(),
        "headline": (analysis.get("headline") or "")[:60],
        "gmail_link": "" if mid.startswith("eml-") else f"https://mail.google.com/mail/u/?authuser={ACCOUNT}#all/{mid}",
        "full_text": full_text,
        "summary": {k: list(s.get(k, [])) for k in ("toc", "points", "changes", "watch_next")},
        "articles": articles,
    }


def index_entry(issue: dict) -> dict:
    return {
        **{k: issue[k] for k in ("id", "newsletter", "newsletter_name", "number", "title", "date", "headline")},
        "articles": [{k: a[k] for k in ("idx", "title", "summary", "countries", "genres")} for a in issue["articles"]],
    }


def prior_context(index: dict, data_dir: Path, key_bytes: bytes, newsletter: str, before_date: str) -> list[dict]:
    """同じ誌の直前3号（古い順）。変化の比較用に号数・タイトル・要点だけ渡す。"""
    prev = [i for i in index["issues"] if i["newsletter"] == newsletter and i["date"] < before_date]
    prev.sort(key=lambda i: i["date"], reverse=True)
    out = []
    for e in reversed(prev[:3]):
        ctx = {"number": e["number"], "title": e["title"], "headline": e["headline"]}
        p = data_dir / "issues" / f"{e['id']}.json.enc"
        try:
            s = crypto_util.read_enc(p, key_bytes)["summary"]
            ctx["points"], ctx["toc"] = s.get("points", []), s.get("toc", [])
        except Exception:
            ctx["article_titles"] = [a["title"] for a in e["articles"]]
        out.append(ctx)
    return out


def run(source, analyzer, data_dir: Path, key_bytes: bytes, *, backfill=False, limit=None,
        dry_run=False, push=None) -> dict:
    """push: (issue_dict) -> None を渡すと新規号ごとに呼ぶ（None なら通知しない）。"""
    data_dir = Path(data_dir)
    state_p, index_p = data_dir / "state.json.enc", data_dir / "index.json.enc"
    state = crypto_util.read_enc(state_p, key_bytes) if state_p.exists() else {"processed": {}, "ignored": []}
    state.setdefault("processed", {})
    state.setdefault("ignored", [])
    index = crypto_util.read_enc(index_p, key_bytes) if index_p.exists() else {"updated_at": "", "issues": []}

    ids = source.list_ids(all_pages=backfill)
    known = set(state["processed"]) | set(state["ignored"])
    new_ids = [i for i in ids if i not in known]
    log(f"gmail: {len(ids)} messages, {len(new_ids)} unseen")

    # 件名の判定（メタデータのみ）。古い順に並べる
    cands = []
    for mid in new_ids:
        try:
            meta = source.get_meta(mid)
        except Exception as e:
            log(f"meta failed id={mid} {safe_err(e)}")
            continue
        key = classify(meta["subject"])
        if key is None:
            state["ignored"].append(mid)
        else:
            cands.append((meta["date_ms"], mid, key))
    cands.sort()
    if limit is not None:
        cands = cands[:limit]
    log(f"matching: {len(cands)} to process")

    done, failed, new_issues = 0, 0, []
    for date_ms, mid, key in cands:
        try:
            msg = source.get_message(mid)
            if dry_run:
                log(f"dry-run id={mid} newsletter={key} chars={len(msg['text'])} subject={'yes' if msg['subject'] else 'no'}")
                done += 1
                continue
            full_text = strip_footer(msg["text"])
            if not full_text.strip():
                raise ValueError("empty body")
            lines, numbered = number_lines(full_text)
            date_iso = datetime.fromtimestamp(msg["date_ms"] / 1000, JST).isoformat()
            prior = prior_context(index, data_dir, key_bytes, key, date_iso)
            analysis = analyzer.analyze(NEWSLETTERS[key][1], msg["subject"], numbered, prior)
            issue = build_issue(key, mid, {**msg, "text": full_text}, analysis)
            crypto_util.write_enc(data_dir / "issues" / f"{issue['id']}.json.enc", issue, key_bytes)
            index["issues"] = [i for i in index["issues"] if i["id"] != issue["id"]] + [index_entry(issue)]
            index["issues"].sort(key=lambda i: i["date"], reverse=True)
            index["updated_at"] = datetime.now(JST).isoformat(timespec="seconds")
            state["processed"][mid] = issue["id"]
            crypto_util.write_enc(index_p, index, key_bytes)
            crypto_util.write_enc(state_p, state, key_bytes)
            new_issues.append(issue)
            done += 1
            log(f"processed id={issue['id']} articles={len(issue['articles'])} chars={len(full_text)}")
        except Exception as e:
            failed += 1
            log(f"failed id={mid} {safe_err(e)}")

    if not dry_run:
        crypto_util.write_enc(state_p, state, key_bytes)  # ignored の更新も保存
        if new_issues and push is not None:
            for issue in new_issues:
                try:
                    push(issue)
                except Exception as e:
                    log(f"push failed id={issue['id']} {safe_err(e)}")
    log(f"done: processed={done} failed={failed}")
    return {"processed": done, "failed": failed, "new_issues": new_issues}


def make_push():
    import apns
    cfg = apns.ApnsConfig.from_env()
    if cfg is None:
        log("apns: not configured, skip")
        return None

    def push(issue: dict) -> None:
        n = issue.get("number")
        body = (f"第{n}号 " if n else "") + issue["title"]
        if issue["headline"]:
            body += "\n" + issue["headline"]
        status = apns.send(cfg, issue["newsletter_name"], body, issue["id"])
        log(f"apns id={issue['id']} http={status}")
    return push


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="過去分を全部、古い順に処理")
    ap.add_argument("--dry-run", action="store_true", help="Claude/APNsを呼ばず、data/にも書かない")
    ap.add_argument("--limit", type=int, default=None, help="処理する号数の上限（古い順）")
    ap.add_argument("--no-push", action="store_true", help="APNs通知を送らない")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    a = ap.parse_args(argv)

    if not NEWSLETTERS:
        log("error: no NEWSLETTER_CONFIG (env or .secrets/newsletter_config.json)")
        return 2

    try:
        import gmail_source
        info = gmail_source.load_token_info()
    except Exception as e:  # 壊れたトークンでもトレースバックを出さない
        log(f"fatal: {safe_err(e)}")
        return 1
    if info is None:
        log("error: no Gmail token (GMAIL_TOKEN_JSON or .secrets/gmail_token.json)")
        return 2
    try:
        key_bytes = crypto_util.load_key()
        import inbox
        source = inbox.InboxSource(gmail_source.GmailSource(info), Path(a.data_dir) / "inbox", key_bytes)
        analyzer = None
        if not a.dry_run:
            import analyzer as an
            analyzer = an.ClaudeAnalyzer()
        push = None if (a.dry_run or a.no_push or a.backfill) else make_push()
        res = run(source, analyzer, Path(a.data_dir), key_bytes, backfill=a.backfill,
                  limit=a.limit, dry_run=a.dry_run, push=push)
    except Exception as e:  # 例外メッセージに本文が混ざらないよう型名のみ
        log(f"fatal: {safe_err(e)}")
        return 1
    return 1 if res["failed"] and not res["processed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
