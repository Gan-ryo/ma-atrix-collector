#!/usr/bin/env python3
"""
MA-ATRIX 集計レポート生成
articles.csv を読み込み、レベル × 評価軸の件数集計表を HTML で出力する。
"""

import csv
import json
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
    "組織":                         "組織",
    "制度・仕組み":                  "制度・仕組み",
    "コンプライアンス":               "コンプラ",
    "生成AI活用対象の業務プロセス":    "業務プロセス",
    "データマネジメント":             "データ管理",
    "生成AI活用":                    "AI活用",
    "生成AIの業務プロセスへの統合":    "業務統合",
}


def load_articles():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_matrix(rows):
    """(level, axis) → [articles] のマップを返す"""
    matrix = defaultdict(list)
    for row in rows:
        axis  = row.get("主要評価軸", "").strip()
        level = row.get("推定レベル", "").strip()
        if axis in AXES and level.isdigit():
            matrix[(int(level), axis)].append(row)
    return matrix


def cell_color(count, max_count):
    if count == 0:
        return "#f8f9fa"
    intensity = count / max_count if max_count > 0 else 0
    # 薄い青 → 濃い青
    r = int(255 - intensity * 180)
    g = int(255 - intensity * 120)
    b = 255
    return f"rgb({r},{g},{b})"


def articles_to_json(articles):
    """モーダル表示用の記事データをJSON文字列で返す"""
    data = [
        {
            "title":   a["タイトル"],
            "url":     a["URL"],
            "company": a.get("企業名", ""),
            "source":  a.get("ソース", ""),
            "date":    a.get("公開日", "")[:10],
            "reasoning": a.get("判定根拠", ""),
        }
        for a in articles
    ]
    return json.dumps(data, ensure_ascii=False)


def generate_html(rows, matrix):
    total = len(rows)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    max_count = max((len(v) for v in matrix.values()), default=1)

    # 行合計・列合計
    row_totals = {lv: sum(len(matrix[(lv, ax)]) for ax in AXES) for lv in LEVELS}
    col_totals = {ax: sum(len(matrix[(lv, ax)]) for lv in LEVELS) for ax in AXES}

    # ── テーブル行生成 ──
    table_rows_html = ""
    for lv in LEVELS:
        cells = ""
        for ax in AXES:
            articles = matrix[(lv, ax)]
            count    = len(articles)
            bg       = cell_color(count, max_count)
            if count > 0:
                json_data = articles_to_json(articles).replace("'", "&#39;")
                cells += (
                    f'<td style="background:{bg}" class="data-cell clickable" '
                    f'onclick="showModal({lv}, \'{ax}\', {json_data})">'
                    f'<span class="count">{count}</span></td>'
                )
            else:
                cells += f'<td style="background:{bg}" class="data-cell"><span class="count zero">—</span></td>'

        total_cell = row_totals[lv]
        table_rows_html += (
            f'<tr>'
            f'<th class="level-header">{LEVEL_LABELS[lv]}</th>'
            f'{cells}'
            f'<td class="total-cell">{total_cell}</td>'
            f'</tr>\n'
        )

    # 列合計行
    col_total_cells = "".join(
        f'<td class="total-cell">{col_totals[ax]}</td>' for ax in AXES
    )

    # ── ヘッダー行 ──
    header_cells = "".join(
        f'<th class="axis-header"><span class="axis-full">{ax}</span>'
        f'<span class="axis-short">{AXIS_SHORT[ax]}</span></th>'
        for ax in AXES
    )

    html = f"""<!DOCTYPE html>
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
  }}
  h1 {{
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 4px;
  }}
  .meta {{
    font-size: 0.8rem;
    color: #666;
    margin-bottom: 20px;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    overflow-x: auto;
    padding: 20px;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    min-width: 700px;
  }}
  th, td {{
    border: 1px solid #dee2e6;
    text-align: center;
    padding: 10px 8px;
    font-size: 0.85rem;
  }}
  .level-header {{
    background: #1a1a2e;
    color: #fff;
    font-weight: 600;
    white-space: nowrap;
    text-align: left;
    padding-left: 12px;
    width: 110px;
  }}
  .axis-header {{
    background: #2d2d5e;
    color: #fff;
    font-weight: 600;
    font-size: 0.78rem;
    vertical-align: bottom;
    padding: 10px 6px;
  }}
  .axis-short {{ display: none; }}
  .data-cell {{ transition: opacity 0.15s; }}
  .data-cell.clickable {{ cursor: pointer; }}
  .data-cell.clickable:hover {{ opacity: 0.75; outline: 2px solid #4a6cf7; }}
  .count {{ font-size: 1.1rem; font-weight: 700; }}
  .count.zero {{ color: #ccc; font-size: 0.9rem; font-weight: 400; }}
  .total-cell {{
    background: #f1f3f9;
    font-weight: 700;
    color: #2d2d5e;
    font-size: 0.95rem;
  }}
  th.total-cell {{
    background: #2d2d5e;
    color: #fff;
  }}
  /* モーダル */
  .modal-overlay {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: 100;
    align-items: center;
    justify-content: center;
  }}
  .modal-overlay.open {{ display: flex; }}
  .modal {{
    background: #fff;
    border-radius: 12px;
    width: min(680px, 95vw);
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
  }}
  .modal-header {{
    padding: 16px 20px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }}
  .modal-title {{ font-size: 1rem; font-weight: 700; color: #1a1a2e; }}
  .modal-subtitle {{ font-size: 0.78rem; color: #888; margin-top: 2px; }}
  .modal-close {{
    background: none; border: none; cursor: pointer;
    font-size: 1.4rem; color: #888; flex-shrink: 0;
    line-height: 1;
  }}
  .modal-close:hover {{ color: #333; }}
  .modal-body {{ overflow-y: auto; padding: 16px 20px; }}
  .article-item {{
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
  }}
  .article-item:last-child {{ margin-bottom: 0; }}
  .article-title {{
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  .article-title a {{
    color: #1a1a2e;
    text-decoration: none;
  }}
  .article-title a:hover {{ text-decoration: underline; color: #4a6cf7; }}
  .article-meta {{
    font-size: 0.75rem;
    color: #888;
    margin-bottom: 6px;
  }}
  .article-reasoning {{
    font-size: 0.8rem;
    color: #444;
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
<body>

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

<!-- モーダル -->
<div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-header">
      <div>
        <div class="modal-title" id="modalTitle"></div>
        <div class="modal-subtitle" id="modalSubtitle"></div>
      </div>
      <button class="modal-close" onclick="document.getElementById('modalOverlay').classList.remove('open')">×</button>
    </div>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<script>
const LEVEL_LABELS = __LEVEL_LABELS_JS__;

function showModal(level, axis, articles) {{
  document.getElementById('modalTitle').textContent = axis + '  ' + LEVEL_LABELS[level];
  document.getElementById('modalSubtitle').textContent = articles.length + ' 件';
  const body = document.getElementById('modalBody');
  body.innerHTML = articles.map(a => `
    <div class="article-item">
      <div class="article-title"><a href="${{a.url}}" target="_blank" rel="noopener">${{a.title}}</a></div>
      <div class="article-meta">${{a.source}} ／ ${{a.date}} ${{a.company ? '／ ' + a.company : ''}}</div>
      ${{a.reasoning ? '<div class="article-reasoning">' + a.reasoning + '</div>' : ''}}
    </div>
  `).join('');
  document.getElementById('modalOverlay').classList.add('open');
}}

function closeModal(e) {{
  if (e.target === document.getElementById('modalOverlay')) {{
    document.getElementById('modalOverlay').classList.remove('open');
  }}
}}

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') document.getElementById('modalOverlay').classList.remove('open');
}});
</script>

</body>
</html>
"""

    # JS用レベルラベル埋め込み
    level_labels_js = json.dumps({str(k): v for k, v in LEVEL_LABELS.items()}, ensure_ascii=False)
    html = html.replace("__LEVEL_LABELS_JS__", level_labels_js)
    return html


def main():
    rows    = load_articles()
    matrix  = build_matrix(rows)
    html    = generate_html(rows, matrix)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"出力完了: {HTML_PATH.resolve()}  （集計: {len(rows)} 件）")


if __name__ == "__main__":
    main()
