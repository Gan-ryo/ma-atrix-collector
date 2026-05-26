# MA-ATRIX News Collector

## プロジェクトの目的
ニュースリリースサイト（PR TIMES / PR Newswire）から定期的にAI関連記事を抽出し、
それらがMA-ATRIXのどの評価軸のどのレベルに相当するかの情報・企業名を付加して蓄積する。

---

## MA-ATRIXとは
生成AI活用の組織成熟度を評価するフレームワーク。

### 評価軸（7軸）
1. 組織
2. 制度・仕組み
3. コンプライアンス
4. 生成AI活用対象の業務プロセス
5. データマネジメント
6. 生成AI活用
7. 生成AIの業務プロセスへの統合

### 成熟度レベル（0〜5）
- 0: 未実施・把握なし
- 1: 属人的・場当たり的
- 2: 基本方針・手順が明文化
- 3: 全社的に標準化・体系化
- 4: 定量的に管理・継続改善
- 5: 継続的最適化・迅速な変化対応

詳細定義は `ma-atrix-def.md` を参照。

---

## アーキテクチャ

```
GitHub Actions（毎日JST 10:00 に定期実行）
    ↓
collector.py
    ├─ feedparser  → PR TIMES RSS / PR Newswire RSS 取得
    ├─ キーワードフィルタ（AI関連記事のみ抽出）
    ├─ Claude API（claude-haiku-4-5）
    │    ├─ MA-ATRIX評価軸・レベル分類
    │    └─ 企業名抽出
    └─ data/articles.csv にコミット・プッシュ
```

### 使用技術・サービス
| 役割 | 技術 | 備考 |
|---|---|---|
| 定期実行 | GitHub Actions | 無償枠内 |
| RSS取得 | feedparser | 無償 |
| AI分類・企業名抽出 | Claude API（claude-haiku-4-5） | $1.00/$5.00 per 1M tokens、プロンプトキャッシュ対応 |
| 蓄積 | GitHubリポジトリ（CSV） | `GITHUB_TOKEN` で自動コミット |

### Claude APIの利用方針
- **バッチ処理**: 5記事/リクエストでまとめて分類（APIコール数を削減）
- **プロンプトキャッシュ**: システムプロンプトを `cache_control: ephemeral` でキャッシュ。2回目以降のバッチはキャッシュ読み取り料金（約1/10）が適用される
- **スキーマ自動マイグレーション**: CSV列定義（HEADERS）変更時、起動時に既存CSVを自動変換

---

## CSVの列定義（data/articles.csv）

| 列名 | 内容 |
|---|---|
| 記事ID | URLのMD5ハッシュ先頭12文字（重複防止キー） |
| 収集日時(UTC) | 収集実行時刻 |
| ソース | PR TIMES / PR Newswire |
| タイトル | 記事タイトル |
| URL | 記事URL |
| 公開日 | RSS配信日時 |
| 概要(先頭200字) | 本文サマリー（HTMLタグ除去済み） |
| **企業名** | 記事に登場する企業名（`、`区切り） |
| 軸1_組織 〜 軸7_業務統合 | 各評価軸の成熟度レベル（0〜5、null=非該当） |
| 主要評価軸 | 最も関連する評価軸名 |
| 推定レベル | 主要評価軸の成熟度レベル |
| 判定根拠 | 80字以内の判定説明 |

---

## 環境変数（GitHub Secrets）

| 変数名 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API キー（必須） |
| `GITHUB_TOKEN` | Actions が自動付与するため設定不要 |

---

## レポート機能

`generate_report.py` を実行すると `report.html` を生成する。

### 機能
- **集計表**: 縦＝成熟度レベル（Lv0〜5）× 横＝評価軸（7軸）の件数ヒートマップ
- **アンカーナビゲーション**: 表の数字をクリックするとページ下部の該当記事セクションへスクロール
- **記事詳細セクション**: 各セルに対応する記事一覧（タイトル・企業名・判定根拠を表示）
- **記事リンク**: 各記事タイトルが元記事URLへの直接リンク（新しいタブで開く）
- **表に戻る**: 各セクション右上の「▲ 表に戻る」で集計表へ戻れる

### 実行方法
```bash
python generate_report.py
# → report.html を出力
```

---

## ファイル構成

```
ma-atrix-collector/
├─ CLAUDE.md                # このファイル（要件定義）
├─ collector.py             # メイン処理（定期収集・分類・CSV保存）
├─ generate_report.py       # レポートHTML生成
├─ backfill_companies.py    # 企業名バックフィル（スキーマ変更時の補完用）
├─ check_companies.py       # 企業名欠損チェックユーティリティ
├─ requirements.txt         # 依存ライブラリ（feedparser, anthropic）
├─ ma-atrix-def.md          # MA-ATRIXフレームワーク定義
├─ report.html              # 集計レポート（generate_report.py で生成）
├─ data/
│  └─ articles.csv          # 蓄積データ（自動生成・毎日追記）
└─ .github/
   └─ workflows/
      └─ collect.yml        # 定期実行ワークフロー（JST 10:00）
```

---

## 経緯・決定事項

### Google Sheetsが使えない（解決済み）
当初はGoogle Sheetsへの蓄積を予定していたが、
組織のGCP環境で `iam.disableServiceAccountKeyCreation` ポリシーが適用されており、
サービスアカウントキーの作成が不可。
→ **GitHubリポジトリにCSVで保存する方式に変更**

### Gemini APIから Claude APIへ移行（解決済み）
当初はGemini 1.5 Flash APIを使用していたが、無料枠が20RPD（1日20リクエスト）と
極めて少なく、50件超の記事処理で429エラーが頻発。
→ **Claude API（claude-haiku-4-5）に移行**。バッチ処理＋プロンプトキャッシュで
　コスト効率よく運用（$5チャージで半年以上の見込み）
