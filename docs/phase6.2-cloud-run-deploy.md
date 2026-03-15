# Phase 6.2: Cloud Run デプロイ + Secret Manager + Supabase

Cloud Runにデプロイし、本番環境で動作する状態にする。

## ゴール

Cloud Run上でプラン生成APIが動く状態にする。Phase 6.3（自動実行）の前提基盤。

## 前提

- Phase 6.1 でDockerコンテナがローカルで動作すること
- GCPプロジェクトが作成済みであること
- Supabase PostgreSQL が利用できること

## やること

### 環境判定 (`run_coach/cloud.py`)

- [x] `is_cloud_run()` — `K_SERVICE` 環境変数で Cloud Run を判定
- [x] ローカル開発には一切影響しない設計

### settings.yaml のgit管理化

- [x] `.gitignore` から `config/settings.yaml` を除外
- [x] `calendar_id` フィールド追加（Cloud Runでは共有カレンダーIDを設定）
- [x] `gcs_config_bucket` フィールド追加（GCSバケット名）
- [x] `config.py` の `DEFAULT_SETTINGS` に新フィールド追加

### GCS操作 (`run_coach/gcs.py`)

- [x] `download_file()` — 単一ファイルダウンロード
- [x] `upload_file()` — 単一ファイルアップロード
- [x] `download_directory()` — プレフィックス配下を一括ダウンロード
- [x] `upload_directory()` — ディレクトリを一括アップロード

### Google Calendar認証（Workload Identity）

- [x] `_get_calendar_service()` に Cloud Run 分岐追加
  - ローカル: 現行の OAuth フロー（変更なし）
  - Cloud Run: `google.auth.default(scopes=SCOPES)` で ADC 認証
- [x] `calendarId` を `_calendar_id` モジュール変数に変更（`set_calendar_id()` で設定）
- [x] `fetch_calendar` / `sync_plan_to_calendar` の `CLIENT_SECRET_PATH` チェックに `is_cloud_run()` 分岐追加

### Garmin認証（GCSトークン保存方式）

Cloud Runはステートレスなので `~/.garminconnect` のトークン保存方式が使えない。
GCSにトークンを保存し、起動時に復元する方式を採用する。

- [x] `_get_tokenstore()` — ローカル=`~/.garminconnect` / Cloud Run=`/tmp/.garminconnect`
- [x] `prefetch_tokens(settings)` — GCSからトークンをダウンロードする公開関数
- [x] `_upload_tokens_to_gcs()` — 認証後にGCSへトークンを書き戻し
- [x] `_login()` フロー: 認証後、Cloud RunではGCSに書き戻し

```
起動時: GCSからトークン取得 → /tmpに復元
  ↓
認証: トークンで認証（期限切れならパスワードでフォールバック）
  ↓
認証後: 更新されたトークンをGCSに書き戻し
```

### profile.yaml のGCSダウンロード

- [x] `ensure_profile(settings)` — Cloud Run時にGCSから `config/profile.yaml` をダウンロード
- [x] API lifespan で Cloud Run 時に呼び出し

### Secret Manager

- [ ] `GARMIN_EMAIL` / `GARMIN_PASSWORD`
- [ ] `OPENAI_API_KEY`
- [ ] `DATABASE_URL`（Supabase接続文字列）
- [ ] Cloud Runから環境変数として注入（`--set-secrets`）

### DB接続（Supabase）

- [ ] Supabase PostgreSQL への接続設定
- [ ] Transaction Pooler を使用（ポート `6543`）
- [ ] 接続文字列に `+psycopg` を手動追加（psycopg3使用のため）
- [ ] `DATABASE_URL` で接続先を管理

### マイグレーション

- [x] CDパイプラインでデプロイ前に `alembic upgrade head` を実行
- [x] `DATABASE_URL` は GitHub Secrets から取得
- [x] Cloud Run の `entrypoint.sh` では `K_SERVICE` 設定時にマイグレーションをスキップ
- [x] ローカル Docker Compose では従来通り entrypoint.sh で実行

### Cloud Run デプロイ

- [x] GitHub Actions CDワークフロー (`.github/workflows/cd.yml`)
- [x] Workload Identity Federation（キーレス認証）
- [x] `--allow-unauthenticated=false`
- [x] リージョン: `asia-northeast1`

### API lifespan 初期化順序

```python
1. load_settings() + apply_settings()
2. Cloud Runの場合: ensure_profile() + prefetch_tokens()
3. check_connection()
```

### Dockerfile

- [x] `COPY config/settings.yaml config/settings.yaml`（git管理版を使用）
- [x] profile.yaml の COPY は不要（Cloud RunではGCSから取得）

### Makefile

- [x] `make upload-profile` — profile.yaml を GCS にアップロード

## テスト

- [x] `tests/test_cloud.py` — `is_cloud_run()` の判定テスト
- [x] `tests/test_gcs.py` — GCSダウンロード/アップロードのモックテスト
- [x] `tests/test_calendar_cloud.py` — ADC認証分岐、calendar_id切り替えテスト

### 本番動作確認

- [ ] Cloud Run上で `/health` が応答すること
- [ ] Secret Managerから認証情報を取得できること
- [ ] Supabase PostgreSQL に接続して `workouts` / `workout_splits` を読めること
- [ ] `POST /internal/coach` でプラン生成が実行されること

## GCP準備手順

### 1. APIの有効化
```bash
gcloud config set project YOUR_PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  calendar-json.googleapis.com \
  iamcredentials.googleapis.com \
  artifactregistry.googleapis.com
```

### 2. Secret Manager にシークレット登録
```bash
echo -n "your-email" | gcloud secrets create GARMIN_EMAIL --data-file=-
echo -n "your-password" | gcloud secrets create GARMIN_PASSWORD --data-file=-
echo -n "sk-..." | gcloud secrets create OPENAI_API_KEY --data-file=-
echo -n "postgresql+psycopg://..." | gcloud secrets create DATABASE_URL --data-file=-

# Cloud Runサービスアカウントにアクセス権付与
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in GARMIN_EMAIL GARMIN_PASSWORD OPENAI_API_KEY DATABASE_URL; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 3. GCSバケット作成
```bash
BUCKET_NAME="run-coach-config-${PROJECT_NUMBER}"
gcloud storage buckets create gs://${BUCKET_NAME} \
  --location=asia-northeast1 \
  --uniform-bucket-level-access

gcloud storage buckets add-iam-policy-binding gs://${BUCKET_NAME} \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin"

# 初期データをアップロード
gsutil -m cp -r ~/.garminconnect/* gs://${BUCKET_NAME}/garmin-tokens/
gsutil cp config/profile.yaml gs://${BUCKET_NAME}/config/profile.yaml
```

### 4. Workload Identity Federation（GitHub Actions用）
```bash
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-condition="assertion.repository=='fuzztarou/run-coach'"

gcloud iam service-accounts create run-coach-deployer \
  --display-name="Run Coach Deployer"

DEPLOY_SA="run-coach-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${DEPLOY_SA}" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${DEPLOY_SA}" \
  --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${DEPLOY_SA}" \
  --role="roles/storage.admin"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${DEPLOY_SA}" \
  --role="roles/artifactregistry.writer"

gcloud iam service-accounts add-iam-policy-binding ${DEPLOY_SA} \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/fuzztarou/run-coach"
```

GitHub Secrets/Varsに設定:
- `WIF_PROVIDER`: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- `WIF_SERVICE_ACCOUNT`: `run-coach-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com`
- `DATABASE_URL`: Supabase接続文字列
- `RUN_COACH_GCS_BUCKET` (Vars): バケット名

### 5. Google Calendar共有設定
1. Google Calendarで「Run Coach」専用カレンダーを作成
2. カレンダーIDを取得（`abc123@group.calendar.google.com` 形式）
3. Cloud Runのサービスアカウントに「予定の変更」権限で共有
4. `config/settings.yaml` の `calendar_id` にカレンダーIDを設定

## Supabase準備手順

1. https://supabase.com/dashboard でプロジェクト作成（リージョン: Northeast Asia / Tokyo）
2. Project Settings > Database > Connection string > **Transaction Pooler** を選択（ポート `6543`）
3. 接続文字列のスキーム部分に `+psycopg` を手動追加
4. 初回マイグレーション: `DATABASE_URL="postgresql+psycopg://..." uv run alembic upgrade head`
5. Supabase Dashboard > Table Editor で `workouts`, `workout_splits` を確認

## 動作確認

```bash
# Health check
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://run-coach-XXXXX-an.a.run.app/health

# プラン生成
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://run-coach-XXXXX-an.a.run.app/internal/coach

# GCSトークン確認
gsutil ls gs://${BUCKET_NAME}/garmin-tokens/
```

## 対象外（Phase 6.3）

- Cloud Scheduler
- 自動実行（週次トリガー）
- リトライ / 障害対応
