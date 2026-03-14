"""FastAPI アプリケーション。HTTP経由でランニングプランを生成する。"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Request, Response

from run_coach.auth import require_oidc
from run_coach.cloud import is_cloud_run
from run_coach.config import apply_settings, ensure_profile, load_profile, load_settings
from run_coach.database import check_connection
from run_coach.garmin import prefetch_tokens
from run_coach.graph import compile_graph
from run_coach.line import WebhookPayloadError, parse_webhook_body
from run_coach.look_back import (
    check_and_prompt_new_activity,
    handle_look_back_reply,
)
from run_coach.state import AgentState

logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "GARMIN_EMAIL",
    "GARMIN_PASSWORD",
    "OPENAI_API_KEY",
    "RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN",
    "RUN_COACH_LINE_USER_ID",
    "RUN_COACH_LINE_CHANNEL_SECRET",
    "RUN_COACH_GCS_BUCKET",
    "GOOGLE_CALENDAR_ID",
    "RUN_COACH_ALLOWED_SA",
]


def _validate_env() -> None:
    """Cloud Runで必須の環境変数が設定されているかチェックする。"""
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """起動時に設定読み込み・DB接続確認を行う。"""
    settings = load_settings()
    apply_settings(settings)
    if is_cloud_run():
        _validate_env()
        ensure_profile()
        prefetch_tokens()
    check_connection()
    yield


app = FastAPI(lifespan=lifespan)

internal_router = APIRouter(
    # internal 配下はOIDC必須にする
    prefix="/internal",
    dependencies=[Depends(require_oidc)],
)


@app.get("/health")
async def health() -> dict[str, bool]:
    """ヘルスチェック。"""
    return {"ok": True}


@internal_router.post("/coach")
async def coach() -> dict:
    """ランニングプランを生成して返す。"""
    profile = load_profile()
    state = AgentState(user_profile=profile)
    graph = compile_graph()
    result = await asyncio.to_thread(graph.invoke, state)
    plan = result["plan"]
    return plan.model_dump(mode="json")


@internal_router.post("/check-new-activity")
async def check_new_activity() -> dict:
    """新着ランを検知して振り返りPromptをLINE Pushする。"""
    prompted_count = check_and_prompt_new_activity()
    return {"prompted": prompted_count}


app.include_router(internal_router)


@app.post("/webhook/line")
async def webhook_line(request: Request) -> Response:
    """LINE Webhookエンドポイント。ユーザーの振り返り返信を受信・保存する。"""
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    try:
        messages = parse_webhook_body(body, signature)
    except WebhookPayloadError as exc:
        return Response(status_code=400, content=str(exc))

    for text, reply_token in messages:
        handle_look_back_reply(text, reply_token)

    return Response(status_code=200, content="OK")
