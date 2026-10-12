# メルマガリーダー（バックエンド）

仕様は `SPEC.md`。有料メルマガの本文を扱うので、**平文をリポジトリ・Actionsログに出さない**（ログは件数・号ID・HTTPステータス・例外の型名だけ）。

## 構成
- `backend/pipeline.py` … Gmail検索 → 新しい号をClaudeで分析 → AES-256-GCM暗号化して `data/` へ → APNs通知
- `backend/crypto_util.py` / `apns.py` / `gmail_source.py` / `analyzer.py` / `textutil.py`
- `backend/decrypt_cat.py` … ローカルで `.enc` を復号して表示
- `.github/workflows/check.yml` … 30分ごと＋手動実行。`data/` に変更があれば commit & push

## Actions secrets
`DATA_KEY` / `GMAIL_TOKEN_JSON` / `ANTHROPIC_API_KEY` / `APNS_KEY_P8`(.p8の中身) / `APNS_KEY_ID` / `APNS_TEAM_ID` / `APNS_DEVICE_TOKEN`
（APNS系が揃っていなければ通知だけ飛ばして続行。本番APNsにするなら環境変数 `APNS_ENV=production`）

## 使い方（ローカル）
```
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest backend/tests -q                 # 偽の Gmail/Claude で暗号化〜復号まで
.venv/bin/python backend/pipeline.py --dry-run --limit 2    # 本物のGmail検索と本文取得だけ。Claude/APNs/書き込みなし
ANTHROPIC_API_KEY=... .venv/bin/python backend/pipeline.py --backfill --no-push   # 過去分を古い順に全部
.venv/bin/python backend/decrypt_cat.py data/index.json.enc
```
オプション: `--backfill`（全ページ検索・通知なし）、`--dry-run`、`--limit N`（古い順にN号）、`--no-push`。

## 運用メモ
- 分析に失敗した号は state に入らず、次の30分後にまた試す（ログに `failed id=...`）。
- 公開リポは60日間リポジトリの動きがないと、定期実行が止められる。号が来れば commit されるので通常は問題ないが、止まったら Actions タブで再有効化。
- 鍵 `DATA_KEY` を変えると既存の `.enc` が全部読めなくなる。変えるなら `data/` を消して `--backfill` し直す。
- 途中で落ちても1号ごとに書き込むので、`--backfill` は再実行すれば続きから処理する（ただしActions上は最後にまとめて commit）。
- 件名が2誌のどちらにも合わないメールは state の `ignored` に入り、再取得しない。

## Privacy

This is a personal, single-user tool. It reads only the repository owner's own Gmail (read-only scope)
to process newsletters the owner subscribes to.

- No data from any other Google account is collected, stored, or shared.
- Newsletter content is encrypted (AES-256-GCM) before it is written to this repository; the key is held
  only by the owner (GitHub Actions secret and the owner's own device).
- Content is sent to the Anthropic API solely to generate summaries for the owner.
- Nothing is sold, shared with third parties, or used for advertising.
- To revoke access: https://myaccount.google.com/permissions

## セキュリティの決めごと

- 記事はすべて同じ鍵（DATA_KEY）で暗号化して公開リポに積んでいる。**鍵が一度でも漏れたら過去の全号が読める**（公開済みの暗号文は消せない）。漏れた疑いがあれば、すぐにリポを非公開にするか削除し、鍵を作り直す。
- 鍵はアプリ本体にも入っているので、**アプリ（ビルドしたもの）を他人に渡さない**。
- 差出人・誌名・Gmail アドレスは secret `NEWSLETTER_CONFIG` にだけ置く（コードに書かない）。
- 依存ライブラリは `backend/requirements.lock`（版とハッシュ値で固定）からだけ入れる。更新するときは
  `uv pip compile backend/requirements.txt --generate-hashes --python-version 3.12 --python-platform x86_64-unknown-linux-gnu -o backend/requirements.lock`
- Actions のログに出してよいのは件数・号ID・HTTPステータス・例外の型名だけ。`print` を足すときは必ずこの方針に合わせる。
