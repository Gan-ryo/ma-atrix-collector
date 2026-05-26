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

import anthropic
import feedparser

# ─────────────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
CSV_PATH            = Path("data/articles.csv")
MAX_PER_FEED        = 200   # 1フィードあたりの最大処理件数
CLAUDE_INTERVAL_SEC = 2.0  # バッチ間のウェイト（APIへの礼儀）
BATCH_SIZE          = 5    # 1リクエストでまとめて分類する記事数
RSS_USER_AGENT      = (
    "Mozilla/5.0 (compatible; MA-ATRIX-Collector/1.0; "
    "+https://github.com/Gan-ryo/ma-atrix-collector)"
)

# ─────────────────────────────────────────────────────
# RSSフィード定義
# ─────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "source": "PR TIMES",
        "url":    "https://prtimes.jp/index.rdf",  # 旧: rss.php は404のため変更
    },
    {
        "source": "PR Newswire",
        "url":    "https://www.prnewswire.com/rss/news-releases-list.rss",  # 旧: BusinessWire AI feedは廃止
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
#   SYSTEM_PROMPT  → 毎回変わらない定義部分（Claudeのプロンプトキャッシュ対象）
#   classify_articles_batch() 内でユーザーメッセージに記事を埋め込む
# ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
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
ユーザーから渡された記事をそれぞれ分析し、MA-ATRIXのどの評価軸のどのレベルに
相当する取り組みを報告しているか判定してください。
- 関連する評価軸すべてにレベル（数値）を付与してください
- 最も主要な評価軸を1つ選んでください
- 生成AI活用と無関係な記事は not_relevant: true としてください
- 結果はJSON配列として返し、記事の番号順に対応させてください
- コードブロック記号（```）は不要です

## 各要素の出力形式
{
  "not_relevant": false,
  "axes": {
    "組織": null,
    "制度・仕組み": null,
    "コンプライアンス": null,
    "生成AI活用対象の業務プロセス": null,
    "データマネジメント": null,
    "生成AI活用": null,
    "生成AIの業務プロセスへの統合": null
  },
  "primary_axis": "評価軸名",
  "primary_level": 0,
  "reasoning": "判定根拠（80字以内）"
}
"""


# ─────────────────────────────────────────────────────
# RSS 取得・フィルタリング
# ─────────────────────────────────────────────────────
def fetch_articles(feed: dict) -> list[dict]:
    """RSSフィードからAI関連記事を取得・フィルタする"""
    print(f"  フィード取得中: {feed['url']}")
    parsed = feedparser.parse(
        feed["url"],
        request_headers={"User-Agent": RSS_USER_AGENT},
    )

    # 診断情報
    status = getattr(parsed, "status", "N/A")
    total  = len(parsed.entries)
    print(f"  HTTPステータス: {status} / 取得エントリ数: {total} 件")
    if parsed.bozo:
        print(f"  [WARN] フィード解析エラー: {parsed.bozo_exception}")
    if total == 0:
        print(f"  [WARN] エントリが0件のため処理をスキップします")
        return []

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
# Claude による MA-ATRIX 分類（バッチ処理 + プロンプトキャッシュ）
# ─────────────────────────────────────────────────────
def classify_articles_batch(client: anthropic.Anthropic, articles: list[dict]) -> list[dict | None]:
    """複数記事をまとめてClaudeに送り、MA-ATRIX評価軸・レベルを一括判定する。

    システムプロンプト（SYSTEM_PROMPT）はキャッシュされるため、
    2回目以降のバッチ呼び出しではキャッシュ読み取り料金（約1/10）が適用される。

    戻り値は articles と同じ長さのリスト。分類失敗の要素は None。
    """
    articles_text = "\n\n".join(
        f"### 記事{i + 1}\nタイトル: {a['title']}\n概要: {a['summary']}"
        for i, a in enumerate(articles)
    )
    user_content = (
        f"{len(articles)}件の記事を分析し、JSON配列で結果を返してください。\n\n"
        f"## 分析対象記事\n{articles_text}\n\n"
        "## 出力（JSON配列のみ）"
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            # SYSTEM_PROMPT は毎回同じ → cache_control でキャッシュ
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_content}],
        )

        # キャッシュ使用状況をデバッグ表示
        usage = response.usage
        if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
            print(f"    [cache] read={usage.cache_read_input_tokens} / "
                  f"created={usage.cache_creation_input_tokens}")

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            print(f"  [WARN] バッチ結果がリストではありません: {type(results)}")
            return [None] * len(articles)
        # 件数が合わない場合は末尾を None で補完
        while len(results) < len(articles):
            results.append(None)
        return results[:len(articles)]
    except json.JSONDecodeError as e:
        print(f"  [WARN] バッチJSON解析失敗: {e}")
        return [None] * len(articles)
    except anthropic.APIStatusError as e:
        print(f"  [WARN] Claude APIエラー: {e.status_code} {e.message}")
        return [None] * len(articles)
    except Exception as e:
        print(f"  [WARN] Claude バッチエラー: {e}")
        return [None] * len(articles)


# ─────────────────────────────────────────────────────
# CSV 操作
# ─────────────────────────────────────────────────────
def load_existing_ids() -> set[str]:
    """既に蓄積済みの記事IDセットを返す（重複防止）"""
    if not CSV_PATH.exists():
        return set()
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return {row["記事ID"] for row in reader}


def append_row(article: dict, result: dict) -> None:
    """1記事分のデータをCSVに追記する"""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    write_header = not CSV_PATH.exists()
    # BOM はファイル新規作成時のみ付与。追記時に utf-8-sig を使うとファイル中間に
    # BOM が挿入されて壊れるため、追記は通常 utf-8 を使う。
    encoding = "utf-8-sig" if write_header else "utf-8"
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

    with CSV_PATH.open("a", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────
def main():
    print(f"=== MA-ATRIX Collector 開始: {datetime.now().isoformat()} ===\n")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY が設定されていません。"
            "GitHub Secrets に ANTHROPIC_API_KEY を登録してください。"
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    existing_ids = load_existing_ids()
    print(f"既存蓄積記事数: {len(existing_ids)} 件\n")

    total_new = 0

    for feed in RSS_FEEDS:
        print(f"【{feed['source']}】")
        articles = fetch_articles(feed)
        new_articles = [a for a in articles if a["id"] not in existing_ids]
        print(f"  AI関連記事: {len(articles)} 件 / うち新規: {len(new_articles)} 件")

        # バッチ単位で分類処理
        for batch_start in range(0, len(new_articles), BATCH_SIZE):
            batch = new_articles[batch_start: batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(new_articles) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"  [バッチ {batch_num}/{total_batches}] {len(batch)}件を分類中...")

            results = classify_articles_batch(client, batch)

            for article, result in zip(batch, results):
                print(f"  ▶ {article['title'][:55]}...")

                if result is None:
                    print("    → 分類失敗、スキップ")
                    continue

                if result.get("not_relevant"):
                    print("    → MA-ATRIX関連なし、スキップ")
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

            time.sleep(CLAUDE_INTERVAL_SEC)

        print()

    print(f"=== 完了: 新規蓄積 {total_new} 件 ===")


if __name__ == "__main__":
    main()
