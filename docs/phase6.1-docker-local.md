# Phase 6.1: Dockerfile + ローカルDocker実行

ローカルでDockerコンテナとしてrun-coachを動かせる状態にする。

## ゴール

`docker compose up` でプラン生成が動く状態にする。Cloud Runデプロイ（Phase 6.2）の前提基盤。

## 前提

- Phase 5 でPostgreSQL移行が完了していること
- ローカルにDockerがインストール済みであること

## やること

### Dockerfile

- [ ] マルチステージビルド（uvベース）
- [ ] Python + 依存パッケージのインストール
- [ ] `run_coach/` と `config/` をコピー
- [ ] FastAPIをuvicornで起動

### FastAPIアプリ

- [ ] `run_coach/api.py` 作成
- [ ] `POST /generate` — LangGraphのプラン生成を実行
- [ ] `GET /health` — ヘルスチェック

```python
@app.post("/generate")
async def generate() -> dict:
    """プラン生成を実行"""
    ...

@app.get("/health")
async def health() -> dict:
    return {"ok": True}
```

### docker-compose.yml

- [ ] `app` サービス（run-coachコンテナ）
- [ ] `db` サービス（PostgreSQL）
- [ ] 環境変数はホストの `.zprofile` から `environment` で渡す
- [ ] ボリューム設定（DBデータ永続化）

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: run_coach
      POSTGRES_PASSWORD: run_coach
      POSTGRES_DB: run_coach
    ports:
      - "${DB_PORT:-5433}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  app:
    build: .
    ports:
      - "${APP_PORT:-8080}:8080"
    environment:
      - DATABASE_URL=postgresql://run_coach:run_coach@db:5432/run_coach
      - GARMIN_EMAIL=${GARMIN_EMAIL}
      - GARMIN_PASSWORD=${GARMIN_PASSWORD}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db

volumes:
  pgdata:
```

※ `DB_PORT` / `APP_PORT` は `config/settings.yaml` の値を使う。docker-compose起動時に渡す。

### 環境変数

ホストの `.zprofile` で定義済みの環境変数を `docker compose` が自動で展開する（`${VAR}` 構文）。追加の設定ファイルは不要。

## テスト方針

- [ ] `docker compose up` でコンテナが起動すること
- [ ] `GET /health` が `{"ok": true}` を返すこと
- [ ] `POST /generate` でプラン生成が実行されること
- [ ] 既存テスト（Phase 1〜5）がコンテナ内でも通ること
- [ ] DB接続: コンテナ内からPostgreSQLにワークアウトデータを読み書きできること

## 対象外（Phase 6.2以降）

- Cloud Runデプロイ
- Secret Manager
- Cloud Scheduler
- サービスアカウント認証
- Garminトークンのステートレス対応
