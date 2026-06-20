#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""実CSVから得意先・品名・金額をダミーデータに置き換えたサンプルCSVを生成"""

import csv, random, os

SRC  = "/Users/takanoakihito/Desktop/受注明細一覧_20260620.csv"
DST  = os.path.join(os.path.dirname(__file__), "サンプルデータ.csv")

random.seed(42)

# ── ダミー得意先名 ──────────────────────────────────────────────
PREFIXES = ["東京","大阪","名古屋","横浜","福岡","札幌","仙台","広島","神戸","京都",
            "埼玉","千葉","川崎","新潟","浜松","熊本","岡山","相模","姫路","長崎"]
TYPES    = ["印刷","パッケージ","商事","製作所","工業","フィルム","産業","テック",
            "クリエイト","デザイン","ラベル","メディア","サプライ","プリント","加工"]
SUFFIXES = ["㈱","㈲","(株)","(有)",""]

def fake_company(n):
    p = PREFIXES[n % len(PREFIXES)]
    t = TYPES[(n * 7 + 3) % len(TYPES)]
    s = SUFFIXES[n % len(SUFFIXES)]
    return f"{p}{t}{s}"

# ── ダミー品名 ──────────────────────────────────────────────────
MATERIALS = ["OPP","PET","NY","PE","CPP","EVOH","AL","紙","不織布","透明"]
PRODUCTS  = ["フィルム","袋","ラベル","シート","パウチ","ロール","テープ","チューブ","カップ","トレー"]
SIZES     = ["50μ","75μ","100μ","125μ","150μ","200μ","250μ","300μ","500μ","1000μ"]
COLORS    = ["透明","白","黒","赤","青","緑","銀","金","クリア","マット"]

def fake_product(n):
    m = MATERIALS[n % len(MATERIALS)]
    p = PRODUCTS[(n * 3 + 1) % len(PRODUCTS)]
    s = SIZES[(n * 5 + 2) % len(SIZES)]
    c = COLORS[(n * 2 + 4) % len(COLORS)]
    return f"{m} {p} {s} {c}"

# ── 変換マップ構築 ──────────────────────────────────────────────
def build_maps(rows):
    customers = sorted(set(r[2].strip() for r in rows if r[2].strip()))
    products  = sorted(set(r[4].strip() for r in rows if r[4].strip()))
    c_map = {c: fake_company(i) for i, c in enumerate(customers)}
    p_map = {p: fake_product(i) for i, p in enumerate(products)}
    return c_map, p_map

def fake_amount(original):
    try:
        v = int(original.strip())
        # 元の桁数を維持しつつランダム化
        if v == 0:
            return "0"
        magnitude = 10 ** (len(str(abs(v))) - 1)
        return str(random.randint(magnitude, magnitude * 10 - 1))
    except Exception:
        return original

# ── メイン ──────────────────────────────────────────────────────
with open(SRC, "r", encoding="cp932", errors="replace") as f:
    reader = csv.reader(f)
    header = next(reader)
    rows   = list(reader)

c_map, p_map = build_maps(rows)

out_rows = []
prod_counter = {}

for row in rows:
    r = row[:]
    # 得意先 [2]
    if r[2].strip() in c_map:
        r[2] = c_map[r[2].strip()]
    # 得意先注文No [3] → 連番ダミー
    if r[3].strip():
        r[3] = f"ORD-{random.randint(10000,99999)}"
    # 品名1 [4]
    key = r[4].strip()
    if key:
        if key not in prod_counter:
            prod_counter[key] = fake_product(len(prod_counter))
        r[4] = prod_counter[key]
    # 品名2 [5]
    if r[5].strip():
        r[5] = ""
    # 受注金額 [9]
    r[9] = fake_amount(r[9])
    # 納品金額 [56]
    r[56] = fake_amount(r[56])
    out_rows.append(r)

with open(DST, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(out_rows)

print(f"生成完了: {DST}")
print(f"  得意先: {len(c_map)} 社 → ダミー名に置換")
print(f"  品名: {len(prod_counter)} 種 → ダミー名に置換")
print(f"  金額: ランダム値に置換")
