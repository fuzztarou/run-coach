# Phase 6: Cloud Run + Cloud Scheduler デプロイ

Cloud Runにデプロイし、自動実行環境を構築する。

## ゴール

Macを閉じていても自動でプラン生成が動く状態にする。Phase 7（LINE通知）の前提基盤。

## 前提

- Phase 5 でPostgreSQL移行が完了していること
- Supabase PostgreSQL を利用できること
- Garmin / OpenAI / Google Calendar の認証情報をSecret Managerで管理できること
- HTTPエンドポイント用に `FastAPI` を採用すること

## フロー

### 週次プラン生成

```mermaid
flowchart TB
    CS[Cloud Scheduler<br>毎週月曜朝] -->|HTTP| CR

    subgraph CR[Cloud Run: run-coach]
        FG[fetch_garmin] --> FC[fetch_calendar<br>Google Calendar API]
        FG --> DB[(Supabase<br>PostgreSQL)]
        FC --> FW[fetch_weather]
        FW --> GR[ガードレール]
        GR --> GEN[LLM: プラン生成]
        GEN --> CHK[セルフチェック]
        CHK -->|OK| OUT[output_plan<br>+ Calendar同期]
        CHK -->|NG| GEN
    end

    OUT -.->|Phase 7| LINE[LINE Push通知]

    style CS fill:#4a9eff,color:#fff
    style CR fill:#f5f5f5,color:#333
```

## やること

### Cloud Run デプロイ

- [ ] Dockerfile作成
- [ ] FastAPIアプリ作成（`/generate`, `/health`）
- [ ] Cloud Runサービスのデプロイ
- [ ] Cloud Schedulerの設定（週次プラン生成トリガー）
- [ ] Supabase接続設定（`DATABASE_URL` / pooler）
- [ ] Google Calendar APIのサービスアカウント設定
- [ ] Secret Managerで認証情報を管理（Garmin / OpenAI / Google Calendar）

### HTTPエンドポイント

- [ ] `/generate` — Cloud Schedulerから呼ばれ、プラン生成 → Calendar同期
- [ ] ヘルスチェック用エンドポイント

## アプリ構成

- Webフレームワークは `FastAPI` を採用する
- `/generate` で LangGraph 実行を起動する
- `/health` でヘルスチェックを返す

```python
@app.post("/generate")
def generate() -> dict:
    ...

@app.get("/health")
def health() -> dict:
    return {"ok": True}
```

## DB接続方針

- Cloud Run から Supabase PostgreSQL へ接続する
- 基本は `DATABASE_URL` で管理する
- 接続先は Supabase の transaction pooler を優先する
- prepared statements 前提の設定は避ける

## 認証方針

### Garmin

- `GARMIN_EMAIL` / `GARMIN_PASSWORD` をSecret Managerで管理
- Cloud Runから環境変数として注入
- `~/.garminconnect` 前提のトークン保存はそのままでは使えない
- トークン永続化方法を別途決める必要がある

### Garmin認証の技術リスク

Cloud Run はステートレスなので、現在の `~/.garminconnect` 保存方式は不安定。

候補:

- 毎回メール+パスワードでログインする
- Secret Manager や GCS にトークンを保存して復元する
- 起動時にトークンを `/tmp` に復元して使う

この点は Phase 6 で先に潰すべき最大の技術リスクとする。

### OpenAI

- `OPENAI_API_KEY` をSecret Managerで管理
- Cloud Runから環境変数として注入

### Google Calendar

- ローカルOAuthトークン前提にはしない
- 専用カレンダーを作成し、サービスアカウントへ共有する
- Cloud Runではサービスアカウント認証でそのカレンダーを読み書きする

## リトライ / 障害対応方針

- Cloud Scheduler 側でHTTP失敗時のリトライを設定する
- Garmin API / LLM API の一時的失敗はアプリ側で短いリトライを入れる
- 部分失敗時はログを残し、失敗した週次実行を再実行できるようにする
- DB接続失敗時は `500` を返し、Schedulerに再試行させる

## デプロイ方針

- デプロイ先は Cloud Run
- コンテナは `Dockerfile` からビルドする
- 初期段階では `gcloud run deploy` を手動実行でよい

```bash
gcloud run deploy run-coach \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated=false
```

## テスト方針

- [ ] 既存テスト全通し: Phase 1〜5のテストがCloud Run環境でも通ること
- [ ] 認証: Secret Managerからの認証情報取得が動くか
- [ ] DB接続: Supabaseに接続して `workouts` / `workout_splits` を読めるか
- [ ] HTTPエンドポイント: `/generate` が正しくプラン生成を実行するか
- [ ] E2Eテスト: Cloud Scheduler → Cloud Run の一連の流れ

```python
# テスト例
def test_generate_endpoint(client):
    """/generate エンドポイントが正常に動作するか"""
    response = client.post("/generate")
    assert response.status_code == 200

def test_secret_manager_integration():
    """Secret Managerから認証情報を取得できるか"""
    # モック環境での検証
    secret = get_secret("GARMIN_EMAIL")
    assert secret is not None
```
