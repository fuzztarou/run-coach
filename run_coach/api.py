"""FastAPI アプリケーション。HTTP経由でランニングプランを生成する。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from run_coach.cloud import is_cloud_run
from run_coach.config import apply_settings, ensure_profile, load_profile, load_settings
from run_coach.database import check_connection
from run_coach.garmin import prefetch_tokens
from run_coach.graph import compile_graph
from run_coach.state import AgentState


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
