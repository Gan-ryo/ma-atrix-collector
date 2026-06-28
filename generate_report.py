#!/usr/bin/env python3
"""
MA-ATRIX 集計レポート生成
articles.csv を読み込み、レベル × 評価軸の件数集計表を HTML で出力する。
数字をクリックするとページ下部の該当記事一覧へジャンプする。
"""

import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CSV_PATH  = Path("data/articles.csv")
HTML_PATH = Path("report.html")

AXES = [
    "組織",
    "制度・仕組み",
    "コンプライアンス",
    "生成AI活用対象の業務プロセス",
    "データマネジメント",
    "生成AI活用",
    "生成AIの業務プロセスへの統合",
]
LEVELS = [0, 1, 2, 3, 4, 5]

LEVEL_LABELS = {
    0: "Lv0 未実施",
    1: "Lv1 属人的",
    2: "Lv2 明文化",
    3: "Lv3 標準化",
    4: "Lv4 定量管理",
    5: "Lv5 最適化",
}

AXIS_SHORT = {
    "組織":                      "組織",
    "制度・仕組み":               "制度",
    "コンプライアンス":            "コンプラ",
    "生成AI活用対象の業務プロセス": "業務PRS",
    "データマネジメント":          "データ",
    "生成AI活用":                 "AI活用",
    "生成AIの業務プロセスへの統合": "業務統合",
}


def cell_id(lv: int, ax: str) -> str:
    return f"s{lv}-{AXES.index(ax)}"


def load_articles():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_matrix(rows):
    matrix = defaultdict(list)
    for row in rows:
        axis  = (row.get("主要評価軸") or "").strip()
        level = (row.get("推定レベル") or "").strip()
        if axis in AXES and level.isdigit():
            matrix[(int(level), axis)].append(row)
    return matrix


def cell_color(count, max_count):
    if count == 0:
        return "#f5f6f8"
    intensity = count / max_count if max_count > 0 else 0
    r = int(255 - intensity * 180)
    g = int(255 - intensity * 120)
    b = 255
    return f"rgb({r},{g},{b})"


def generate_html(rows, matrix):
    total        = len(rows)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    max_count    = max((len(v) for v in matrix.values()), default=1)

    row_totals = {lv: sum(len(matrix[(lv, ax)]) for ax in AXES) for lv in LEVELS}
    col_totals = {ax: sum(len(matrix[(lv, ax)]) for lv in LEVELS) for ax in AXES}

    # ── テーブルヘッダー ──
    header_cells = "".join(
        f'<th class="axis-header">'
        f'<span class="axis-full">{ax}</span>'
        f'<span class="axis-short">{AXIS_SHORT[ax]}</span>'
        f'</th>'
        for ax in AXES
    )

    # ── テーブル本体 ──
    table_rows_html = ""
    for lv in LEVELS:
        cells = ""
        for ax in AXES:
            arts  = matrix[(lv, ax)]
            count = len(arts)
            bg    = cell_color(count, max_count)
            if count > 0:
                anchor = cell_id(lv, ax)
                cells += (
                    f'<td style="background:{bg}" class="data-cell">'
                    f'<a class="cell-link" href="#{anchor}">{count}</a>'
                    f'</td>'
                )
            else:
                cells += f'<td style="background:{bg}" class="data-cell"><span class="zero">—</span></td>'

        table_rows_html += (
            f'<tr>'
            f'<th class="level-header">{LEVEL_LABELS[lv]}</th>'
            f'{cells}'
            f'<td class="total-cell">{row_totals[lv]}</td>'
            f'</tr>\n'
        )

    col_total_cells = "".join(
        f'<td class="total-cell">{col_totals[ax]}</td>' for ax in AXES
    )

    # ── 記事詳細セクション ──
    detail_sections = ""
    for lv in LEVELS:
        for ax in AXES:
            arts = matrix[(lv, ax)]
            if not arts:
                continue
            anchor = cell_id(lv, ax)
            cards  = ""
            for a in arts:
                url      = a.get("URL", "#")
                title    = a.get("タイトル", "（タイトルなし）")
                company  = a.get("企業名", "")
                source   = a.get("ソース", "")
                pub      = a.get("公開日", "")[:10]
                reasoning = a.get("判定根拠", "")
                meta_parts = [p for p in [source, pub, company] if p]
                meta = " ／ ".join(meta_parts)
                cards += f"""
        <div class="article-card">
          <div class="article-title">
            <a href="{url}" target="_blank" rel="noopener">{title}</a>
          </div>
          <div class="article-meta">{meta}</div>
          {"" if not reasoning else f'<div class="article-reasoning">{reasoning}</div>'}
        </div>"""

            detail_sections += f"""
  <section class="detail-section" id="{anchor}">
    <div class="section-header">
      <div class="section-label">
        <span class="tag-level">{LEVEL_LABELS[lv]}</span>
        <span class="tag-axis">{ax}</span>
        <span class="tag-count">{len(arts)} 件</span>
      </div>
      <a class="back-link" href="#top">▲ 表に戻る</a>
    </div>
    {cards}
  </section>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA-ATRIX 記事集計レポート</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
  padding: 24px;
  scroll-behavior: smooth;
}}
h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }}
.meta {{ font-size: 0.8rem; color: #666; margin-bottom: 20px; }}

/* ── 集計表 ── */
.card {{
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  overflow-x: auto;
  padding: 20px;
  margin-bottom: 32px;
}}
table {{ border-collapse: collapse; width: 100%; min-width: 700px; }}
th, td {{
  border: 1px solid #dee2e6;
  text-align: center;
  padding: 10px 8px;
  font-size: 0.85rem;
}}
.level-header {{
  background: #1a1a2e; color: #fff; font-weight: 600;
  white-space: nowrap; text-align: left; padding-left: 12px; width: 110px;
}}
.axis-header {{
  background: #2d2d5e; color: #fff; font-weight: 600;
  font-size: 0.78rem; vertical-align: bottom; padding: 10px 6px;
}}
.axis-short {{ display: none; }}
.data-cell {{ padding: 0; }}
.cell-link {{
  display: block; width: 100%; padding: 10px 8px;
  font-size: 1.1rem; font-weight: 700; color: #1a1a2e;
  text-decoration: none; transition: background 0.15s;
}}
.cell-link:hover {{ background: rgba(74,108,247,0.15); color: #4a6cf7; }}
.zero {{ color: #ccc; font-size: 0.9rem; }}
.total-cell {{ background: #f1f3f9; font-weight: 700; color: #2d2d5e; }}
th.total-cell {{ background: #2d2d5e; color: #fff; }}

/* ── 記事詳細セクション ── */
.detail-section {{
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  padding: 20px 24px;
  margin-bottom: 24px;
  scroll-margin-top: 16px;
}}
.section-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}}
.section-label {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.tag-level {{
  background: #1a1a2e; color: #fff;
  font-size: 0.78rem; font-weight: 700;
  padding: 3px 10px; border-radius: 999px;
}}
.tag-axis {{
  background: #eef0ff; color: #2d2d5e;
  font-size: 0.82rem; font-weight: 600;
  padding: 3px 10px; border-radius: 999px;
}}
.tag-count {{
  background: #f0f2f5; color: #666;
  font-size: 0.78rem;
  padding: 3px 8px; border-radius: 999px;
}}
.back-link {{
  font-size: 0.78rem; color: #888; text-decoration: none;
}}
.back-link:hover {{ color: #4a6cf7; }}
.article-card {{
  border: 1px solid #e8eaf0;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 10px;
}}
.article-card:last-child {{ margin-bottom: 0; }}
.article-title {{ font-size: 0.9rem; font-weight: 600; margin-bottom: 4px; }}
.article-title a {{ color: #1a1a2e; text-decoration: none; }}
.article-title a:hover {{ text-decoration: underline; color: #4a6cf7; }}
.article-meta {{ font-size: 0.75rem; color: #888; margin-bottom: 6px; }}
.article-reasoning {{
  font-size: 0.8rem; color: #444;
  background: #f8f9ff;
  border-left: 3px solid #4a6cf7;
  padding: 6px 10px;
  border-radius: 0 4px 4px 0;
}}

@media (max-width: 640px) {{
  .axis-full {{ display: none; }}
  .axis-short {{ display: inline; }}
  .level-header {{ font-size: 0.72rem; width: 72px; }}
}}
</style>
</head>
<body id="top">

<h1>MA-ATRIX 記事集計レポート</h1>
<p class="meta">集計対象: {total} 件 ／ 生成日時: {generated_at}</p>

<div class="card">
  <table>
    <thead>
      <tr>
        <th class="level-header" style="background:#2d2d5e">レベル \\ 評価軸</th>
        {header_cells}
        <th class="total-cell" style="background:#1a1a2e;color:#fff">合計</th>
      </tr>
    </thead>
    <tbody>
      {table_rows_html}
      <tr>
        <th class="level-header">合計</th>
        {col_total_cells}
        <td class="total-cell">{total}</td>
      </tr>
    </tbody>
  </table>
</div>

{detail_sections}

</body>
</html>
"""


def main():
    rows   = load_articles()
    matrix = build_matrix(rows)
    html   = generate_html(rows, matrix)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"出力完了: {HTML_PATH.resolve()}  （集計: {len(rows)} 件）")


if __name__ == "__main__":
    main()
