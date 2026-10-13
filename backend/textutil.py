"""本文の整形（フッター除去）と、国名・ジャンルの正規化。"""
from __future__ import annotations

import re

FOOTER_MARKERS = re.compile(
    r"配信停止|配信解除|配信を停止|購読解除|購読停止|メール配信の停止|解除はこちら|"
    r"unsubscribe|このメールは.{0,30}(配信|送信)|本メールは.{0,30}(配信|送信)|"
    r"心当たりがない|お心当たり|送信専用|返信できません|Copyright|©|"
    r"課金に関するお問い合わせ|購読アドレスの変更",
    re.I,
)
DECORATION = re.compile(r"^[\s\-=_*━─―＝■□◆◇▼▽●○・.─-╿]*$")


def strip_footer(text: str) -> str:
    """末尾の配信停止案内などを落とす。本文側は一切書き換えない。

    末尾25%（最低でも最後の30行）の範囲にある最初のフッター目印行から後ろを落とす。
    落とす量が全体の40%を超えるときは誤検出とみなして何もしない。
    """
    lines = text.split("\n")
    n = len(lines)
    window_start = min(int(n * 0.75), max(n - 30, 0))
    cut = None
    for i in range(window_start, n):
        if FOOTER_MARKERS.search(lines[i]):
            cut = i
            break
    if cut is None:
        return text.strip("\n")
    # 目印行の直前にある区切り線・空行も一緒に落とす
    while cut > 0 and DECORATION.match(lines[cut - 1]):
        cut -= 1
    if (n - cut) > n * 0.4:
        return text.strip("\n")
    return "\n".join(lines[:cut]).strip("\n")


COUNTRY_ALIASES = {
    "アメリカ": "米国", "米": "米国", "米国": "米国", "アメリカ合衆国": "米国", "合衆国": "米国",
    "USA": "米国", "US": "米国", "U.S.": "米国", "United States": "米国", "トランプ政権": "米国",
    "中華人民共和国": "中国", "中": "中国", "China": "中国", "中国本土": "中国",
    "日": "日本", "Japan": "日本",
    "ロシア連邦": "ロシア", "露": "ロシア", "Russia": "ロシア",
    "ウクライナ": "ウクライナ", "Ukraine": "ウクライナ",
    "大韓民国": "韓国", "南朝鮮": "韓国", "韓": "韓国", "South Korea": "韓国",
    "朝鮮民主主義人民共和国": "北朝鮮", "North Korea": "北朝鮮",
    "中華民国": "台湾", "Taiwan": "台湾",
    "India": "インド", "Iran": "イラン", "Israel": "イスラエル",
    "イギリス": "英国", "英": "英国", "UK": "英国", "United Kingdom": "英国", "大英帝国": "英国",
    "France": "フランス", "仏": "フランス", "Germany": "ドイツ", "独": "ドイツ",
    "欧州連合": "EU", "European Union": "EU", "イーユー": "EU",
    "Brazil": "ブラジル", "ブラジル連邦共和国": "ブラジル",
    "サウジ": "サウジアラビア", "トルコ共和国": "トルコ", "Turkey": "トルコ", "トルキエ": "トルコ",
    "ヨーロッパ": "欧州", "ヨーロッパ連合": "EU", "中近東": "中東",
}

GENRES = [
    "国内政治", "選挙", "外交", "安全保障・軍事", "経済・通商", "金融・市場",
    "エネルギー・資源", "技術・AI", "ビジネス・企業", "健康・医療", "社会・人権", "戦争・紛争", "その他",
]
GENRE_ALIASES = {
    "政治": "国内政治", "内政": "国内政治", "安全保障": "安全保障・軍事", "軍事": "安全保障・軍事",
    "防衛": "安全保障・軍事", "経済": "経済・通商", "通商": "経済・通商", "貿易": "経済・通商",
    "金融": "金融・市場", "市場": "金融・市場", "エネルギー": "エネルギー・資源", "資源": "エネルギー・資源",
    "技術": "技術・AI", "AI": "技術・AI", "テクノロジー": "技術・AI", "人権": "社会・人権",
    "社会": "社会・人権", "戦争": "戦争・紛争", "紛争": "戦争・紛争",
    "ビジネス": "ビジネス・企業", "企業": "ビジネス・企業", "経営": "ビジネス・企業",
    "健康": "健康・医療", "医療": "健康・医療",
}


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def normalize_countries(items) -> list[str]:
    out = []
    for c in items or []:
        c = str(c).strip()
        out.append(COUNTRY_ALIASES.get(c, c))
    return _dedupe(out)


def normalize_genres(items) -> list[str]:
    out = []
    for g in items or []:
        g = str(g).strip()
        g = GENRE_ALIASES.get(g, g)
        out.append(g if g in GENRES else "その他")
    out = _dedupe(out)[:3]
    return out or ["その他"]
