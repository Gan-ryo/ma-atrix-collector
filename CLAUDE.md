# MA-ATRIX News Collector

## プロジェクトの目的
ニュースリリースサイト（PR TIMES / BusinessWire）から定期的にAI関連記事を抽出し、
それらがMA-ATRIXのどの評価軸のどのレベルに相当するかの情報を付加して蓄積する。

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
    ├─ feedparser  → PR TIMES RSS / BusinessWire RSS 取得
    ├─ キーワードフィルタ（AI関連記事のみ抽出）
    ├─ Gemini 1.5 Flash API → MA-ATRIX評価軸・レベル分類
    └─ 蓄積先（後述）
```

### 使用技術・サービス
| 役割 | 技術 | 備考 |
|---|---|---|
| 定期実行 | GitHub Actions | 無償枠内 |
| RSS取得 | feedparser | 無償 |
| AI分類 | Gemini 1.5 Flash API | 無償枠: 15RPM / 1,500RPD |
| 蓄積 | 未定（下記「現在の課題」参照） | |

---

## 現在の課題・決定事項

### Google Sheetsが使えない
当初はGoogle Sheetsへの蓄積を予定していたが、
組織のGCP環境で `iam.disableServiceAccountKeyCreation` ポリシーが適用されており、
サービスアカウントキーの作成が不可。

### 対応方針：GitHubリポジトリにCSVで保存
- `GITHUB_TOKEN`（Actions自動付与）を使ってCSVをリポジトリにコミット
- Google Cloud不要、追加Secrets不要（Gemini APIキーのみでよい）
- **collector.py をCSV保存方式に書き直すのが次のタスク**

---

## 環境変数（GitHub Secrets）

| 変数名 | 内容 |
|---|---|
| `GEMINI_API_KEY` | Gemini API キー（必須） |
| `GITHUB_TOKEN` | Actions が自動付与するため設定不要 |

---

## ファイル構成

```
ma-atrix-collector/
├─ CLAUDE.md              # このファイル
├─ collector.py           # メイン処理（CSV保存方式に要修正）
├─ requirements.txt       # 依存ライブラリ
├─ ma-atrix-def.md        # MA-ATRIXフレームワーク定義
├─ data/
│  └─ articles.csv        # 蓄積データ（自動生成）
└─ .github/
   └─ workflows/
      └─ collect.yml      # 定期実行ワークフロー
```

---

## 次のタスク

1. `collector.py` の蓄積部分をGoogle Sheets → CSV（リポジトリコミット）に書き直す
2. `collect.yml` に git commit/push のステップを追加する
3. ローカルで動作確認してからGitHubにプッシュ
