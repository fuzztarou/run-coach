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
| 4. テスト | pytest実行 + `make` で動作確認 |
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
│   ├── config.py          # 設定読み込み (settings.yaml / profile.yaml)
│   ├── graph.py           # LangGraph グラフ定義
│   ├── prompt.py          # LLM プロンプトテンプレート
│   ├── planner.py         # LLM プラン生成
│   ├── plan_review.py     # セルフチェック（コーチングルール検証）
│   └── formatter.py       # JSON → Markdown 変換
├── tests/                 # テスト
├── docs/                  # Phase毎の詳細設計
├── config/                # 設定ファイル
│   ├── settings.yaml      # アプリケーション設定（LLMモデル等）
│   └── settings.example.yaml
├── DESIGN.md              # 全体設計書
├── pyproject.toml         # uv プロジェクト設定
├── .env.example           # 必要な環境変数の一覧
├── .github/
│   └── workflows/ci.yml   # GitHub Actions (lint + test)
└── .claude/
```

## コマンド

```bash
# 初期セットアップ
uv sync

# 実行（環境変数は.zprofileで定義済み）
uv run python -m run_coach

# テスト
uv run pytest tests/

# lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# 依存追加
uv add <package>
uv add --dev <package>

# Docker / API 動作確認（Makefile）
make help          # コマンド一覧
make up            # app + db 起動
make local-coach     # プラン生成の動作確認（JSON整形出力）
make down          # 停止
```

## ルール

### 必須
- **mainブランチに直接コミットしない。必ずブランチを切ってPRで統合する**
- シークレットをハードコードしない（`.zprofile`の環境変数 / Secret Manager）
- `.env` ファイルは使わない。環境変数はシェル設定ファイルで管理する
- アプリケーション設定（ポート番号等）は `config/settings.yaml` で管理する
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
- 変数名は中身が想像できる具体的な名前にする（`resp` → `event_detail`, `monthly_calendar` など）
- マジックナンバーを使わない。モジュール先頭で定数として定義する
- 各処理は state を受け取り state を返す関数にする（LangGraphノード）
- テストは各Phaseで書く

### テストスタイル
- フラットな `def test_*()` 関数で書く（クラスは使わない）
- HTTPエンドポイントのテストは `TestClient` で実際にリクエストを投げる（`MagicMock()` で Request を作らない）
- 環境変数は `monkeypatch.setenv()` / `monkeypatch.delenv()` を使う（`patch.dict("os.environ")` は使わない）

### セキュリティ
- Garminパスワードはコードに残さない（トークン認証を利用）
- SQLiteファイルのパーミッション: 600
- LINE Webhookは署名検証必須
- Cloud Runは未認証許可 + アプリ層でOIDCトークン検証（`run_coach/auth.py`）

### 認証マトリクス

`/internal/*` 配下は `APIRouter` の `dependencies` でOIDCトークン検証が自動適用される。
内部向けエンドポイントを追加する場合は `internal_router` に登録すること。

| エンドポイント | 認証方式 |
|---|---|
| `GET /health` | なし（公開） |
| `POST /webhook/line` | LINE署名検証 |
| `POST /internal/coach` | OIDCトークン検証（自動） |
| `POST /internal/check-new-activity` | OIDCトークン検証（自動） |
