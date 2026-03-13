"""FastAPI アプリケーション。HTTP経由でランニングプランを生成する。"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response

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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """起動時に設定読み込み・DB接続確認を行う。"""
    settings = load_settings()
    apply_settings(settings)
    if is_cloud_run():
        ensure_profile()
        prefetch_tokens()
    check_connection()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, bool]:
    """ヘルスチェック。"""
    return {"ok": True}


@app.post("/coach")
async def coach() -> dict:
    """ランニングプランを生成して返す。"""
    profile = load_profile()
    state = AgentState(user_profile=profile)
    graph = compile_graph()
    result = await asyncio.to_thread(graph.invoke, state)
    plan = result["plan"]
    return plan.model_dump(mode="json")


@app.post("/check-new-activity")
async def check_new_activity() -> dict:
    """新着ランを検知して振り返りPromptをLINE Pushする。"""
    prompted_count = check_and_prompt_new_activity()
    return {"prompted": prompted_count}


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
