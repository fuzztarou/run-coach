#!/bin/bash
set -e

# Cloud Run ではCDパイプラインでマイグレーション済み。ローカルのみ実行。
if [ -z "$K_SERVICE" ]; then
  alembic upgrade head
fi

exec uvicorn run_coach.api:app --host 0.0.0.0 --port 8080
