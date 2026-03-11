#!/bin/bash
set -e

alembic upgrade head
exec uvicorn run_coach.api:app --host 0.0.0.0 --port 8080
