#!/usr/bin/env python3
"""
MA-ATRIX News Collector
PR TIMES / BusinessWire からAI関連記事を定期収集し、
MA-ATRIXの評価軸・成熟度レベルを付与して data/articles.csv に蓄積する。
"""

import csv
import json
import os
import re
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import google.generativeai as genai

# ─────────────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────────────
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
CSV_PATH            = Path("data/articles.csv")
MAX_PER_FEED        = 50   # 1フィードあたりの最大処理件数（Gemini無償枠対策）
GEMINI_INTERVAL_SEC = 4.5  # 無償枠: 15RPM ≒ 4秒以上の間隔が必要

# ─────────────────────────────────────────────────────
# RSSフィード定義
# ─────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "source": "PR TIMES",
        "url":    "https://prtimes.jp/rss.php",
    },
    {
        "source": "BusinessWire",
        "url":    "https://feed.businesswire.com/rss/home/?rss=G1&label=richtextfile&topicid=AI",
    },
]

# AI関連キーワード（PR TIMESは全件RSSのためこれでフィルタ）
AI_KEYWORDS = [
    # 日本語
    "AI", "人工知能", "生成AI", "ChatGPT", "LLM", "機械学習", "ディープラーニング",
    "深層学習", "大規模言語モデル", "自動化", "Claude", "Gemini", "Copilot",
    "チャットボット", "自然言語", "RAG", "エージェント",
    # 英語
    "artificial intelligence", "generative AI", "machine learning", "deep learning",
    "large language model", "neural network", "NLP", "natural language processing",
    "agentic", "foundation model",
]

# ─────────────────────────────────────────────────────
# CSV 列定義
# ─────────────────────────────────────────────────────
HEADERS = [
    "記事ID", "収集日時(UTC)", "ソース", "タイトル", "URL", "公開日",
    "概要(先頭200字)",
    "軸1_組織", "軸2_制度仕組み", "軸3_コンプライアンス",
    "軸4_業務プロセス", "軸5_データマネジメント",
    "軸6_生成AI活用", "軸7_業務統合",
    "主要評価軸", "推定レベル", "判定根拠",
]

# ─────────────────────────────────────────────────────
# MA-ATRIX 分類プロンプト
# ─────────────────────────────────────────────────────
CLASSIFY_PROMPT = """\
あなたはMA-ATRIXという生成AI活用成熟度フレームワークのアナリストです。

## MA-ATRIXの評価軸（7軸）
1. 組織: ビジョン・戦略・経営層コミットメント・組織文化・予算体制
2. 制度・仕組み: 体制・ルール・教育プログラム・業務統合の制度的枠組み
3. コンプライアンス: 法令遵守・AI倫理・個人情報・著作権・情報セキュリティ
4. 生成AI活用対象の業務プロセス: 対象業務プロセスの定義・標準化・品質管理
5. データマネジメント: データ収集・品質・アクセス性・管理体制
6. 生成AI活用: モデル選定・運用・監視・評価（LLMOps/GenAIOps）
7. 生成AIの業務プロセスへの統合: 業務プロセスへのAI組み込み・全体最適化

## 成熟度レベル（0〜5）
0: 未実施・把握なし
1: 属人的・場当たり的な実施
2: 基本方針・手順が明文化・管理
3: 全社的に標準化・体系化・一貫運用
4: 定量的に管理・統計的分析・継続改善
5: 継続的最適化・迅速な変化対応

## 指示
以下の記事を分析し、MA-ATRIXのどの評価軸のどのレベルに相当する取り組みを報告しているか判定してください。
- 関連する評価軸すべてにレベル（数値）を付与してください
- 最も主要な評価軸を1つ選んでください
- 生成AI活用と無関係な記事は not_relevant: true としてください
- JSONのみを返し、コードブロック記号（```）は不要です

## 出力形式
{{
  "not_relevant": false,
  "axes": {{
    "組織": null,
    "制度・仕組み": null,
    "コンプライアンス": null,
    "生成AI活用対象の業務プロセス": null,
    "データマネジメント": null,
    "生成AI活用": null,
    "生成AIの業務プロセスへの統合": null
  }},
  "primary_axis": "評価軸名",
  "primary_level": 0,
  "reasoning": "判定根拠（80字以内）"
}}

## 分析対象記事
タイトル: {title}
概要: {summary}
"""


# ─────────────────────────────────────────────────────
# RSS 取得・フィルタリング
# ─────────────────────────────────────────────────────
def fetch_articles(feed: dict) -> list[dict]:
    """RSSフィードからAI関連記事を取得・フィルタする"""
    print(f"  フィード取得中: {feed['url']}")
    parsed = feedparser.parse(feed["url"])

    articles = []
    for entry in parsed.entries:
        title   = entry.get("title", "")
        summary = re.sub(r"<[^>]+>", "", entry.get("summary", entry.get("description", "")))
        url     = entry.get("link", "")
        pub     = entry.get("published", entry.get("updated", ""))

        text = (title + " " + summary).lower()
        if not any(kw.lower() in text for kw in AI_KEYWORDS):
            continue

        articles.append({
            "source":  feed["source"],
            "title":   title.strip(),
            "summary": summary[:200].strip(),
            "url":     url,
            "pub":     pub,
            "id":      hashlib.md5(url.encode()).hexdigest()[:12],
        })

        if len(articles) >= MAX_PER_FEED:
            break

    return articles


# ─────────────────────────────────────────────────────
# Gemini による MA-ATRIX 分類
# ─────────────────────────────────────────────────────
def classify_article(model, article: dict) -> dict | None:
    """Gemini 1.5 Flash でMA-ATRIX評価軸・レベルを判定する"""
    prompt = CLASSIFY_PROMPT.format(
        title=article["title"],
        summary=article["summary"],
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    [WARN] JSON解析失敗: {e}")
        return None
    except Exception as e:
        print(f"    [WARN] Gemini エラー: {e}")
        return None


# ─────────────────────────────────────────────────────
# CSV 操作
# ─────────────────────────────────────────────────────
def load_existing_ids() -> set[str]:
    """既に蓄積済みの記事IDセットを返す（重複防止）"""
    if not CSV_PATH.exists():
        return set()
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["記事ID"] for row in reader}


def append_row(article: dict, result: dict) -> None:
    """1記事分のデータをCSVに追記する"""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    write_header = not CSV_PATH.exists()
    axes = result.get("axes", {})
    row = {
        "記事ID":               article["id"],
        "収集日時(UTC)":         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "ソース":                article["source"],
        "タイトル":              article["title"],
        "URL":                  article["url"],
        "公開日":                article["pub"],
        "概要(先頭200字)":       article["summary"],
        "軸1_組織":             axes.get("組織", ""),
        "軸2_制度仕組み":        axes.get("制度・仕組み", ""),
        "軸3_コンプライアンス":  axes.get("コンプライアンス", ""),
        "軸4_業務プロセス":      axes.get("生成AI活用対象の業務プロセス", ""),
        "軸5_データマネジメント": axes.get("データマネジメント", ""),
        "軸6_生成AI活用":        axes.get("生成AI活用", ""),
        "軸7_業務統合":          axes.get("生成AIの業務プロセスへの統合", ""),
        "主要評価軸":            result.get("primary_axis", ""),
        "推定レベル":            result.get("primary_level", ""),
        "判定根拠":              result.get("reasoning", ""),
    }

    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────
def main():
    print(f"=== MA-ATRIX Collector 開始: {datetime.now().isoformat()} ===\n")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    existing_ids = load_existing_ids()
    print(f"既存蓄積記事数: {len(existing_ids)} 件\n")

    total_new = 0

    for feed in RSS_FEEDS:
        print(f"【{feed['source']}】")
        articles = fetch_articles(feed)
        new_articles = [a for a in articles if a["id"] not in existing_ids]
        print(f"  AI関連記事: {len(articles)} 件 / うち新規: {len(new_articles)} 件")

        for article in new_articles:
            print(f"  ▶ {article['title'][:55]}...")

            result = classify_article(model, article)

            if result is None:
                print("    → 分類失敗、スキップ")
                time.sleep(GEMINI_INTERVAL_SEC)
                continue

            if result.get("not_relevant"):
                print("    → MA-ATRIX関連なし、スキップ")
                time.sleep(GEMINI_INTERVAL_SEC)
                continue

            append_row(article, result)
            existing_ids.add(article["id"])
            total_new += 1
            print(
                f"    → 蓄積完了: "
                f"主要軸=【{result.get('primary_axis', '?')}】"
                f" Lv{result.get('primary_level', '?')} "
                f"| {result.get('reasoning', '')[:40]}"
            )

            time.sleep(GEMINI_INTERVAL_SEC)

        print()

    print(f"=== 完了: 新規蓄積 {total_new} 件 ===")


if __name__ == "__main__":
    main()
