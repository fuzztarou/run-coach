# run-coach

ランニング用パーソナルトレーナーAIエージェント

## 実装の流れ

```
調査 → Plan → 実装 → テスト → Review
```

| ステップ | 内容 |
|----------|------|
| 1. 調査 | DESIGN.md・docs/を確認、不明点を質問 |
| 2. Plan | planモードで実装計画、ユーザー承認を得る |
| 3. 実装 | コード実装 |
| 4. テスト | pytest実行 |
| 5. Review | コードレビュー |

## 実装前ルール（必須）

**実装タスクではplanモードを使用すること。**

1. まずDESIGN.mdと該当Phaseのドキュメント(docs/)を読む
2. planモードで実装計画を立てる
3. ユーザーの承認を得てから実装開始

**不明点は選択肢とメリデメを提示し、自分の意見を述べること。**

## プロジェクト構成

```
run-coach/
├── run_coach/             # ソースコード
│   ├── __init__.py
│   ├── __main__.py        # エントリーポイント
│   ├── state.py           # Pydantic スキーマ (AgentState等)
│   ├── garmin.py          # Garmin データ取得
│   ├── calendar.py        # カレンダー取得
│   ├── weather.py         # 天気予報取得
│   ├── guardrails.py      # コーチングルール
│   ├── planner.py         # LLM プラン生成
│   └── formatter.py       # JSON → Markdown 変換
├── tests/                 # テスト
├── docs/                  # Phase毎の詳細設計
├── DESIGN.md              # 全体設計書
├── pyproject.toml         # uv プロジェクト設定
├── .env.tpl               # 1Password参照テンプレート
├── .github/
│   └── workflows/ci.yml   # GitHub Actions (lint + test)
└── .claude/
```

## コマンド

```bash
# 初期セットアップ
uv sync

# 実行（1Password経由）
op run --env-file=.env.tpl -- uv run python -m run_coach

# テスト
uv run pytest tests/

# lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# 依存追加
uv add <package>
uv add --dev <package>
```

## ルール

### 必須
- **mainブランチに直接コミットしない。必ずブランチを切ってPRで統合する**
- シークレットをハードコードしない（1Password CLI / Secret Manager）
- LLMに送るデータは最小限（位置情報・個人情報を除外）
- Pydanticでstateスキーマを定義（型安全）
- LLM出力は構造化JSON（文章ではなくPlan型に準拠）

### ブランチ運用
- ブランチ名: `feat/<機能名>`, `fix/<修正内容>`, `docs/<ドキュメント>`
- PRマージ後にブランチ削除

### 実装計画
- planモードで実装計画を立てたら、ルートフォルダに `PLAN_<機能名>.md` を作成する
- 例: `PLAN_phase1_mvp.md`, `PLAN_guardrails.md`
- 実装完了後も削除せず残す（振り返り用）

### 規約
- 命名: スネークケース
- 各処理は state を受け取り state を返す関数にする（LangGraph移行を見据える）
- テストは各Phaseで書く

### セキュリティ
- Garminパスワードは.envに残さない（トークン認証を利用）
- SQLiteファイルのパーミッション: 600
- LINE Webhookは署名検証必須
- Cloud RunはIAM認証
