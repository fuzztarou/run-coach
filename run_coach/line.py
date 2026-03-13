from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from base64 import b64encode
from datetime import timedelta

from linebot.v3.messaging import (  # type: ignore[import-untyped]
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.rest import ApiException  # type: ignore[import-untyped]

from run_coach.calendar import WORKOUT_TYPE_LABEL
from run_coach.feedback_parser import parse_description
from run_coach.formatter import DAY_OF_WEEK
from run_coach.state import AgentState, Plan

logger = logging.getLogger(__name__)

LINE_MESSAGE_CHAR_LIMIT = 5000


def _get_messaging_api() -> tuple[MessagingApi, ApiClient] | None:
    """MessagingApi を返す。ACCESS_TOKEN 未設定なら None。"""
    token = os.environ.get("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        logger.warning("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN is not set.")
        return None
    configuration = Configuration(access_token=token)
    api_client = ApiClient(configuration)
    return MessagingApi(api_client), api_client


def _push_message(text: str) -> None:
    """LINE Push メッセージを送信する。"""
    user_id = os.environ.get("RUN_COACH_LINE_USER_ID")
    if not user_id:
        logger.warning("RUN_COACH_LINE_USER_ID is not set.")
        return
    result = _get_messaging_api()
    if not result:
        return
    messaging_api, api_client = result
    with api_client:
        messaging_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text, quickReply=None, quoteToken=None)],
                notificationDisabled=False,
                customAggregationUnits=None,
            )
        )


def _reply_message(reply_token: str, text: str) -> None:
    """LINE Reply メッセージを送信する。"""
    result = _get_messaging_api()
    if not result:
        return
    messaging_api, api_client = result
    with api_client:
        messaging_api.reply_message(
            ReplyMessageRequest(
                replyToken=reply_token,
                messages=[TextMessage(text=text, quickReply=None, quoteToken=None)],
                notificationDisabled=False,
            )
        )


def format_plan_for_line(plan: Plan) -> str:
    """Plan を LINE 用テキストに変換する。"""
    day_start = plan.week_start
    day_end = day_start + timedelta(days=6)

    header = (
        "📋 1週間のトレーニング計画\n"
        f"期間: {day_start.month}/{day_start.day}"
        f"({DAY_OF_WEEK[day_start.weekday()]})"
        f" 〜 {day_end.month}/{day_end.day}"
        f"({DAY_OF_WEEK[day_end.weekday()]})"
    )

    parts: list[str] = [header]

    if plan.workout_evaluation:
        parts.extend(["", f"📝 {plan.workout_evaluation}"])

    parts.append("")
    parts.append("─" * 10)

    for workout in plan.workouts:
        day_name = DAY_OF_WEEK[workout.date.weekday()]
        duration = f" {workout.duration_min}min" if workout.duration_min else ""

        workout_label = WORKOUT_TYPE_LABEL.get(
            workout.workout_type, workout.workout_type
        )
        lines = [f"{workout.date.month}/{workout.date.day}({day_name})"]
        lines.append(f"{workout_label}{duration}")
        if workout.max_hr:
            lines.append(f"HR上限{workout.max_hr}")
        if workout.notes:
            lines.append(workout.notes)

        parts.append("\n" + "\n".join(lines))

    if plan.reasoning:
        parts.extend(["", "─" * 10, "", f"💡 {plan.reasoning}"])

    return "\n".join(parts)


def send_plan_notification(plan: Plan) -> None:
    """LINE Push メッセージでプランを送信する。未設定時はスキップ。"""
    message_text = format_plan_for_line(plan)
    if len(message_text) > LINE_MESSAGE_CHAR_LIMIT:
        message_text = message_text[:LINE_MESSAGE_CHAR_LIMIT]

    try:
        _push_message(message_text)
        logger.info("LINE notification sent successfully.")
    except (ApiException, OSError):
        logger.exception("Failed to send LINE notification. Continuing pipeline.")


def notify_line(state: AgentState) -> AgentState:
    """LangGraph ノード: プランを LINE で通知する。"""
    if state.plan:
        send_plan_notification(state.plan)
    return state


# ---------------------------------------------------------------------------
# Phase 7.2: 振り返り対話 (look_back)
# ---------------------------------------------------------------------------


def verify_signature(body: bytes, signature: str) -> bool:
    """LINE Webhook署名を検証する。"""
    channel_secret = os.environ.get("RUN_COACH_LINE_CHANNEL_SECRET", "")
    if not channel_secret:
        logger.error("RUN_COACH_LINE_CHANNEL_SECRET is not set.")
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


class WebhookPayloadError(Exception):
    """Webhook のペイロードが不正な場合の例外。"""


def parse_webhook_body(body: bytes, signature: str) -> list[tuple[str, str]]:
    """LINE Webhookリクエストを検証・パースし、(text, reply_token) のリストを返す。

    署名不正・JSON不正の場合は WebhookPayloadError を送出する。
    テキストメッセージ以外のイベントはスキップする。
    """
    if not verify_signature(body, signature):
        raise WebhookPayloadError("Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WebhookPayloadError("Invalid JSON") from exc

    results: list[tuple[str, str]] = []
    for event in payload.get("events", []):
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue
        text = message.get("text", "")
        reply_token = event.get("replyToken", "")
        results.append((text, reply_token))
    return results


def format_look_back_prompt(workout: dict) -> str:
    """ワークアウト情報から振り返りPromptメッセージを生成する。"""
    workout_date = workout["date"]
    workout_type = WORKOUT_TYPE_LABEL.get(
        workout["workout_type"], workout["workout_type"]
    )
    distance = workout.get("distance_km") or 0
    duration_min = workout.get("duration_min") or 0
    minutes = int(duration_min)
    seconds = int((duration_min - minutes) * 60)
    duration_str = f"{minutes}:{seconds:02d}"

    return (
        f"🏃 ランお疲れさまでした！\n"
        f"{workout_date.month}/{workout_date.day} {workout_type} "
        f"{distance:.1f}km {duration_str}\n"
        f"\n"
        f"以下の形式で振り返りを送ってください：\n"
        f"RPE: (1-10の数値)\n"
        f"痛み: (なし or 部位)\n"
        f"コメント: (自由記述)"
    )


def send_look_back_prompt(workout: dict) -> None:
    """LINE Pushメッセージで振り返りPromptを送信する。"""
    try:
        _push_message(format_look_back_prompt(workout))
        logger.info("Look back prompt sent for workout %s.", workout["id"])
    except (ApiException, OSError):
        logger.exception("Failed to send look_back prompt.")


def parse_look_back_message(text: str) -> dict:
    """ユーザーの振り返りメッセージをパースする。

    parse_description が日本語ラベル（痛み/コメント）にも対応済みのため
    そのまま委譲する。

    Returns:
        {"rpe": int|None, "pain": str|None, "comment": str|None}
    """
    return parse_description(text)


def send_reply(reply_token: str, message_text: str) -> None:
    """LINE ReplyMessageRequestで返信する。"""
    try:
        _reply_message(reply_token, message_text)
        logger.info("Reply sent successfully.")
    except (ApiException, OSError):
        logger.exception("Failed to send reply.")
