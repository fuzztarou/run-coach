.PHONY: help up down build logs ps restart \
       db-up db-down db-logs db-psql \
       migrate migrate-history migrate-new migrate-down \
       local-coach cloud-coach upload-profile \
       gcp-set-project

APP_PORT := $(shell grep '^app_port:' config/settings.yaml 2>/dev/null | awk '{print $$2}')
APP_PORT := $(or $(APP_PORT),8080)

# デフォルトターゲット
help: ## ヘルプ表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker (app + db) ──────────────────────────────

up: ## app + db を起動
	APP_PORT=$(APP_PORT) docker compose up -d --build

down: ## app + db を停止
	docker compose down

build: ## app イメージをリビルド
	docker compose build app

logs: ## app のログを表示 (follow)
	docker compose logs -f app

ps: ## コンテナ状態を表示
	docker compose ps

restart: ## app を再起動
	docker compose restart app

# ── DB のみ ─────────────────────────────────────────

db-up: ## PostgreSQL のみ起動
	docker compose up -d postgres

db-down: ## PostgreSQL のみ停止
	docker compose down postgres

db-logs: ## PostgreSQL のログを表示
	docker compose logs -f postgres

db-psql: ## psql で接続
	docker compose exec postgres psql -U postgres -d run_coach

# ── Alembic マイグレーション ─────────────────────────

migrate: ## マイグレーション実行 (upgrade head)
	uv run alembic upgrade head

migrate-history: ## マイグレーション履歴を表示
	uv run alembic history --verbose

migrate-new: ## 新規マイグレーション作成 (make migrate-new MSG="add users table")
	uv run alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## 1つ前にロールバック
	uv run alembic downgrade -1

# ── API ─────────────────────────────────────────────

local-coach: ## プラン生成 - ローカル (JSON整形出力)
	@curl -s -X POST http://localhost:$(APP_PORT)/coach | jq .

cloud-coach: ## プラン生成 - Cloud Run (JSON整形出力)
	@CLOUD_RUN_URL=$$(gcloud run services describe run-coach --region=asia-northeast1 --format='value(status.url)') && \
	TOKEN=$$(gcloud auth print-identity-token) && \
	curl -s -X POST "$$CLOUD_RUN_URL/coach" -H "Authorization: Bearer $$TOKEN" | jq .

# ── GCP ─────────────────────────────────────────────

gcp-set-project: ## GCPプロジェクトを切り替え（要: RUN_COACH_GCP_PROJECT_ID 環境変数）
	@test -n "$(RUN_COACH_GCP_PROJECT_ID)" || (echo "Error: RUN_COACH_GCP_PROJECT_ID 環境変数が未設定です" && exit 1)
	gcloud config set project $(RUN_COACH_GCP_PROJECT_ID)
	@echo "プロジェクトを $(RUN_COACH_GCP_PROJECT_ID) に切り替えました"

# ── GCS ─────────────────────────────────────────────

upload-profile: ## profile.yaml を GCS にアップロード（要: RUN_COACH_GCS_BUCKET 環境変数）
	@test -n "$(RUN_COACH_GCS_BUCKET)" || (echo "Error: RUN_COACH_GCS_BUCKET 環境変数が未設定です" && exit 1)
	gsutil cp config/profile.yaml gs://$(RUN_COACH_GCS_BUCKET)/config/profile.yaml
	@echo "アップロード完了: gs://$(RUN_COACH_GCS_BUCKET)/config/profile.yaml"
