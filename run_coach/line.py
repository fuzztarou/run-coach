from __future__ import annotations

import logging
import os
from datetime import timedelta

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from run_coach.calendar import WORKOUT_TYPE_LABEL
from run_coach.formatter import DAY_OF_WEEK
from run_coach.state import AgentState, Plan

logger = logging.getLogger(__name__)

LINE_MESSAGE_CHAR_LIMIT = 5000


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
    token = os.environ.get("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("RUN_COACH_LINE_USER_ID")

    if not token or not user_id:
        logger.warning(
            "RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN or RUN_COACH_LINE_USER_ID is not set. "
            "Skipping LINE notification."
        )
        return

    message_text = format_plan_for_line(plan)
    if len(message_text) > LINE_MESSAGE_CHAR_LIMIT:
        message_text = message_text[:LINE_MESSAGE_CHAR_LIMIT]

    try:
        configuration = Configuration(access_token=token)
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=message_text)],
                )
            )
        logger.info("LINE notification sent successfully.")
    except Exception:
        logger.exception("Failed to send LINE notification. Continuing pipeline.")


def notify_line(state: AgentState) -> AgentState:
    """LangGraph ノード: プランを LINE で通知する。"""
    if state.plan:
        send_plan_notification(state.plan)
    return state
