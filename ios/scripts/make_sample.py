#!/usr/bin/env python3
"""ダミーのサンプルデータを SPEC どおりに暗号化して Meruma/Sample/ に出す（実在メルマガの文章は使わない）。"""
import base64, json, os, pathlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = pathlib.Path(__file__).resolve().parent.parent
key = base64.b64decode((ROOT.parent / ".secrets/data_key.b64").read_text().strip())
OUT = ROOT / "Meruma/Sample"
OUT.mkdir(parents=True, exist_ok=True)

def enc(obj):
    n = os.urandom(12)
    ct = AESGCM(key).encrypt(n, json.dumps(obj, ensure_ascii=False).encode(), None)  # ct||tag
    return base64.b64encode(n + ct)

def art(idx, title, body, summary, points, c, g):
    return dict(idx=idx, title=title, body=body, summary=summary, points=points, countries=c, genres=g)

issues = [
 dict(id="nl1-20261012-sample01", newsletter="nl1", newsletter_name="サンプル誌A",
  number=900, title="今週の動き（サンプル）架空の島国の選挙", date="2026-10-12T07:00:00+09:00",
  headline="架空の島国で大統領選が接戦、資源価格と港湾の協定が焦点に",
  gmail_link="https://mail.google.com/mail/u/0/#all/sample01",
  summary=dict(toc=["架空の島国ナミナ共和国の大統領選", "ダミー連邦と周辺国の港湾協定", "半導体の仮想サプライチェーン"],
    points=["ナミナ共和国の大統領選は、現職と挑戦者の差が2ポイント以内で、決選投票になる見込み。", "港湾協定は、船が出入りする港の使い方を国同士で決める約束のこと。今回は使用料の配分が争点。", "半導体の部品は一国に集中しているため、止まると他国の工場も止まる。"],
    changes=["先週は現職が優勢と伝えられていたが、今週は挑戦者が追い上げた。"],
    watch_next=["決選投票の日程と、港湾協定の署名の有無。"]),
  articles=[
   art(0, "ナミナ共和国の大統領選が接戦", "（サンプル本文）ナミナ共和国で行われた大統領選の第1回投票は、現職のアルバ氏が34%、挑戦者のベルタ氏が32%と接戦になった。\n\nどちらも過半数に届かず、2週間後に決選投票が行われる。争点は物価対策と、港の運営を外国企業に任せるかどうかである。\n\n（これは動作確認用に作ったダミーの文章で、実在の出来事ではありません。）",
     "第1回投票は現職34%対挑戦者32%で、決選投票へ。物価と港の運営が争点。", ["決選投票は2週間後", "争点は物価と港の運営"], ["ナミナ共和国"], ["選挙"]),
   art(1, "ダミー連邦と周辺国が港湾協定で綱引き", "（サンプル本文）ダミー連邦は、周辺3か国と結ぶ港湾協定の使用料の配分を見直すよう求めている。\n\n3か国のうち2か国は受け入れの姿勢だが、1か国は輸出品の値上がりを懸念して反対している。協定が結ばれなければ、各国の貨物は遠回りの航路を使うことになり、運賃が上がる見通しだ。",
     "使用料の配分を巡り、3か国のうち1か国が反対。決裂すれば運賃が上がる。", ["使用料の配分が争点", "決裂なら遠回りの航路で運賃上昇"], ["ダミー連邦", "米国"], ["外交", "経済・通商"]),
   art(2, "半導体の部品が一国に集中するリスク", "（サンプル本文）ある仮想の調査では、特殊な部品の9割が1つの国の3工場で作られているという。\n\n工場が止まれば、他の国の組み立てラインも数週間で止まる。各国は在庫の積み増しと、別の調達先の開拓を急いでいる。",
     "特殊部品の9割が3工場に集中。止まれば他国の生産も数週間で止まる。", ["在庫の積み増しが進む", "別の調達先を探す動き"], ["日本", "台湾"], ["技術・AI", "経済・通商"]),
  ]),
 dict(id="nl2-20261011-sample02", newsletter="nl2", newsletter_name="サンプル誌B",
  number=412, title="（サンプル）予算編成と党内の駆け引き", date="2026-10-11T18:30:00+09:00",
  headline="架空の与党内で来年度予算の配分を巡る綱引きが表面化",
  gmail_link="https://mail.google.com/mail/u/0/#all/sample02",
  summary=dict(toc=["予算配分を巡る党内の動き", "選挙区の区割り見直し"],
    points=["与党の派閥Aは防災予算の増額を、派閥Bは子育て支援の拡充を求めている。", "区割りの見直しで、議席が減る県が出る見込み。"],
    changes=[], watch_next=["予算の大枠が示される今月下旬の会合。"]),
  articles=[
   art(0, "予算配分で与党内に温度差", "（サンプル本文）来年度予算の概算要求を前に、与党内で配分を巡る意見が割れている。\n\n派閥Aは防災、派閥Bは子育て支援を重視し、財務担当は全体を抑えたい考えだ。（動作確認用のダミー文です。）",
     "防災と子育て支援のどちらを厚くするかで党内が割れている。", ["防災 vs 子育て支援", "財務担当は抑制の姿勢"], ["日本"], ["国内政治", "経済・通商"]),
   art(1, "区割り見直しで議席が減る県", "（サンプル本文）人口の変化に合わせた区割りの見直し案が出され、2つの県で議席が1つずつ減る見通しになった。\n\n該当県の議員からは反発の声が出ている。",
     "人口変化に合わせた見直しで2県が1議席ずつ減る見通し。", ["2県で各1減", "該当県の議員が反発"], ["日本"], ["国内政治", "選挙"]),
  ]),
 dict(id="nl1-20261005-sample03", newsletter="nl1", newsletter_name="サンプル誌A",
  number=899, title="今週の動き（サンプル）エネルギー価格と北の海", date="2026-10-05T07:00:00+09:00",
  headline="仮想の産ガス国が輸出を絞り、欧州の冬の備えに影",
  gmail_link="https://mail.google.com/mail/u/0/#all/sample03",
  summary=dict(toc=["ガス輸出の削減", "北の海の航路"], points=["産ガス国が輸出量を1割減らすと発表し、欧州の備蓄計画が見直される。", "氷が少ない年は北の海の航路が使え、運ぶ日数が短くなる。"],
    changes=[], watch_next=["欧州各国の備蓄の発表。"]),
  articles=[
   art(0, "産ガス国が輸出を1割削減", "（サンプル本文）仮想の産ガス国ゾルダ共和国は輸出量を1割減らすと発表した。国内の需要増が理由だとしている。\n\n欧州は備蓄の目標を引き上げる方向で調整に入った。（ダミー文です。）",
     "輸出1割減で欧州は備蓄の目標を引き上げる方向。", ["理由は国内需要の増加", "欧州は備蓄目標を上げる"], ["ゾルダ共和国", "EU"], ["エネルギー・資源"]),
   art(1, "北の海の航路が早く開く", "（サンプル本文）今年は氷が少なく、北の海の航路が例年より早く使えるようになった。アジアと欧州を結ぶ日数が約10日短くなる。",
     "氷が少なく航路が早く開通。アジア〜欧州が約10日短縮。", ["日数が約10日短縮"], ["ロシア", "中国"], ["経済・通商", "安全保障・軍事"]),
  ]),
]
for i in issues:
    i["full_text"] = "\n\n――――――\n\n".join(a["title"] + "\n" + a["body"] for a in i["articles"])
def head(i):
    d = {k: i[k] for k in ["id","newsletter","newsletter_name","number","title","date","headline"]}
    d["articles"] = [{k: a[k] for k in ["idx","title","summary","countries","genres"]} for a in i["articles"]]
    return d
(OUT / "sample_index.json.enc").write_bytes(enc({"updated_at": "2026-10-12T12:00:00+09:00", "issues": [head(i) for i in issues]}))
for i in issues:
    (OUT / f"sample_{i['id']}.json.enc").write_bytes(enc(i))
print("ok", len(issues))
