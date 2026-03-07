# run-coach

Garmin Connect のワークアウト履歴をもとに、LLM が来週のトレーニング計画を自動生成する CLI ツール。

## できること

- Garmin Connect から直近2週間のランニング・ウォーキング履歴を取得
- レース予測タイム（5K/10K/ハーフ/フル）を取得
- 履歴を評価し、来週のトレーニング計画を構造化 JSON で生成
- 各ワークアウトに目的・心拍上限・曜日を付与して Markdown 表示

## 出力例

```
## ワークアウト評価

持久力は向上しているが、ペースのバラつきが見られる。
閾値トレーニングを取り入れることでさらなる向上が期待できる。

## 来週のメニュー

| 日付       | 曜日 | メニュー | 目的         | 時間 | 強度 | HR上限 | メモ                   |
|------------|------|----------|-------------|------|------|--------|------------------------|
| 2026-03-09 | 月   | easy_run | 疲労抜き     | 40   | 低   | 140    | 軽めのジョギング         |
| 2026-03-11 | 水   | tempo    | 閾値向上     | 30   | 中   | 160    | レースペースを意識       |
| 2026-03-14 | 土   | long_run | 有酸素ベース | 90   | 低   | 150    | ゆっくりロング走         |
```

## セットアップ

```bash
# 依存インストール
uv sync

# プロフィール設定
cp config/profile.example.yaml config/profile.yaml
# config/profile.yaml を自分の情報に編集
```

### 環境変数

以下の環境変数が必要です：

- `GARMIN_EMAIL` — Garmin Connect のメールアドレス
- `GARMIN_PASSWORD` — Garmin Connect のパスワード
- `OPENAI_API_KEY` — OpenAI API キー

## 使い方

```bash
uv run python -m run_coach
```

初回実行時に Garmin Connect へログインし、トークンが `~/.garminconnect` に保存されます。2回目以降はトークン認証です。

## プロフィール設定

```yaml
# config/profile.yaml
birthday: "1980-10-15"
goal: "サブ4"
runs_per_week:
  min: 3
  max: 4
injury_history:
  - "2025年 左膝IT band"
```

## テスト

```bash
uv run pytest tests/ -v
```

## 技術スタック

- Python + uv
- Pydantic（スキーマ定義・バリデーション）
- garminconnect（Garmin Connect API）
- OpenAI API（GPT-4o-mini）
- gitleaks（pre-commit シークレット検出）
