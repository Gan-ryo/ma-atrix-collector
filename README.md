# MA-ATRIX News Collector

PR TIMES / BusinessWire からAI関連ニュースリリースを定期収集し、  
MA-ATRIXの評価軸・成熟度レベルを自動付与して `data/articles.csv` に蓄積するツールです。

---

## アーキテクチャ

```
GitHub Actions（毎日 JST 10:00）
    ↓
collector.py
    ├─ feedparser  → PR TIMES RSS / BusinessWire RSS 取得
    ├─ Gemini 1.5 Flash → MA-ATRIX評価軸・レベル分類
    └─ csv モジュール   → data/articles.csv に追記
    ↓
git commit & push（新規記事があった場合のみ）
```

---

## セットアップ手順

### 1. Gemini API キーの取得（無償）

1. https://aistudio.google.com/ にアクセス
2. 「Get API key」→「Create API key」
3. 発行されたキーをメモ

> 無償枠: 15リクエスト/分、1日1,500リクエストまで

---

### 2. GitHub リポジトリへのデプロイ

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/{あなた}/ma-atrix-collector.git
git push -u origin main
```

#### 2-1. Secrets の設定

リポジトリの「Settings」→「Secrets and variables」→「Actions」→「New repository secret」

| Secret名 | 値 |
|---|---|
| `GEMINI_API_KEY` | 手順1で取得したAPIキー |

> `GITHUB_TOKEN` は Actions が自動付与するため設定不要です。

---

### 3. Actions の権限確認

リポジトリの「Settings」→「Actions」→「General」→「Workflow permissions」で  
**「Read and write permissions」** を選択してください。  
（ワークフローが `data/articles.csv` をコミット・プッシュするために必要）

---

### 4. 動作確認

GitHub の「Actions」タブ → 「MA-ATRIX News Collector」→「Run workflow」で手動実行できます。  
実行後、`data/articles.csv` がリポジトリに追加・更新されます。

---

## 出力フォーマット（data/articles.csv）

| 列 | 内容 |
|---|---|
| 記事ID | URLのMD5ハッシュ（重複防止キー） |
| 収集日時(UTC) | 実行時刻（UTC） |
| ソース | PR TIMES / BusinessWire |
| タイトル | 記事タイトル |
| URL | 記事URL |
| 公開日 | RSS掲載日時 |
| 概要(先頭200字) | 本文冒頭200字 |
| 軸1〜7 | 各評価軸の推定レベル（0〜5、無関係はblank） |
| 主要評価軸 | 最も関連性の高い評価軸 |
| 推定レベル | 主要評価軸のレベル |
| 判定根拠 | Geminiによる80字以内の説明 |

---

## 無償枠の上限目安

| サービス | 無償枠 | 本ツールの消費 |
|---|---|---|
| GitHub Actions | 月2,000分 | 約5分/日 × 30日 ≒ 150分 |
| Gemini 1.5 Flash | 1日1,500リクエスト | 最大100リクエスト/日 |

---

## カスタマイズ

- **収集頻度の変更**: `collect.yml` の `cron` を編集
- **最大処理件数の変更**: `collector.py` の `MAX_PER_FEED`（デフォルト: 50）を変更
- **キーワード追加**: `collector.py` の `AI_KEYWORDS` リストに追加
- **フィード追加**: `collector.py` の `RSS_FEEDS` リストに追加
