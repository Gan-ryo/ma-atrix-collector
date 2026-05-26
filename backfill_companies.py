#!/usr/bin/env python3
"""
企業名バックフィル
articles.csv の「企業名」列が空の記事に対して Claude API で企業名を抽出し、
CSV を上書き更新する。
"""

import csv
import json
import os
import re
import time
from pathlib import Path

import anthropic

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
CSV_PATH            = Path("data/articles.csv")
BATCH_SIZE          = 5
INTERVAL_SEC        = 2.0

SYSTEM_PROMPT = """\
記事のタイトルと概要から、登場する企業・組織名をすべて抽出してください。
- 株式会社・Inc.・Corp.・Ltd.などの法人格も含める
- 官公庁・自治体・大学なども含める
- 結果はJSON配列のみ返す（コードブロック不要）
- 企業が見当たらない場合は空配列 [] を返す

## 出力形式（JSON配列のみ）
[["企業名1", "企業名2"], ["企業名3"], ...]
各要素が1記事分の企業名リスト。記事の番号順に対応させること。
"""


def extract_companies_batch(client: anthropic.Anthropic, articles: list[dict]) -> list[list[str]]:
    """複数記事から企業名を一括抽出する。戻り値は articles と同じ長さのリスト。"""
    articles_text = "\n\n".join(
        f"### 記事{i + 1}\nタイトル: {a['タイトル']}\n概要: {a['概要(先頭200字)']}"
        for i, a in enumerate(articles)
    )
    user_content = (
        f"{len(articles)}件の記事から企業名を抽出し、JSON配列で返してください。\n\n"
        f"{articles_text}\n\n## 出力（JSON配列のみ）"
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            return [[] for _ in articles]
        while len(results) < len(articles):
            results.append([])
        return results[:len(articles)]
    except Exception as e:
        print(f"  [WARN] バッチエラー: {e}")
        return [[] for _ in articles]


def main():
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY が設定されていません。")

    # CSV 読み込み
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

    targets = [i for i, r in enumerate(rows) if not r.get("企業名", "").strip()]
    print(f"企業名なし: {len(targets)} 件 / 全体: {len(rows)} 件\n")

    if not targets:
        print("バックフィル対象なし。終了します。")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    updated = 0

    for batch_start in range(0, len(targets), BATCH_SIZE):
        batch_indices = targets[batch_start: batch_start + BATCH_SIZE]
        batch_rows    = [rows[i] for i in batch_indices]
        batch_num     = batch_start // BATCH_SIZE + 1
        total_batches = (len(targets) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"[バッチ {batch_num}/{total_batches}] {len(batch_rows)}件を処理中...")

        companies_list = extract_companies_batch(client, batch_rows)

        for idx, companies in zip(batch_indices, companies_list):
            company_str = "、".join(companies)
            rows[idx]["企業名"] = company_str
            title = rows[idx]["タイトル"][:50]
            print(f"  ▶ {title}... → {company_str if company_str else '（なし）'}")
            updated += 1

        time.sleep(INTERVAL_SEC)

    # CSV 書き戻し
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n=== 完了: {updated} 件を更新しました ===")


if __name__ == "__main__":
    main()
