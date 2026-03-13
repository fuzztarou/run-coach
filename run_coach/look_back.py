"""振り返り対話のビジネスロジック。"""

from __future__ import annotations

import logging

from run_coach.converters import pace_str_to_seconds
from run_coach.database import (
    get_engine,
    get_pending_look_back_workout,
    get_workout_by_garmin_id,
    mark_look_back_prompted,
    update_workout_look_back,
    upsert_workouts,
)
from run_coach.garmin import _login, summarize_activity
from run_coach.line import (
    parse_look_back_message,
    send_look_back_prompt,
    send_reply,
)

logger = logging.getLogger(__name__)

# 振り返りチェック対象は最新1件のみ
_LATEST_ACTIVITY_LIMIT = 1


def check_and_prompt_new_activity() -> int:
    """最新ランをチェックし、振り返り未記入なら LINE Push する。

    - Garminから最新1件のみ取得
    - description由来のコメントが既にあれば通知スキップ
    - 既にPrompt送信済みならスキップ

    Returns:
        Prompt送信件数（0 or 1）
    """
    client = _login()
    raw_activities = client.get_activities(start=0, limit=_LATEST_ACTIVITY_LIMIT)
    activities: list[dict] = raw_activities if isinstance(raw_activities, list) else []

    if not activities:
        return 0

    summary = summarize_activity(activities[0])
    if not summary or not summary.garmin_activity_id:
        return 0

    workout_dict = {
        "garmin_activity_id": summary.garmin_activity_id,
        "date": summary.date,
        "workout_type": summary.type,
        "distance_km": summary.distance_km,
        "duration_min": summary.duration_min,
        "pace_seconds_per_km": pace_str_to_seconds(summary.avg_pace),
        "avg_heart_rate_bpm": summary.avg_hr,
        "training_effect": summary.training_effect,
        "description": summary.description or "",
        "rpe": None,
        "pain": None,
        "comment": None,
    }

    engine = get_engine()
    with engine.connect() as conn:
        upsert_workouts(conn, [workout_dict])
        conn.commit()

        workout = get_workout_by_garmin_id(conn, summary.garmin_activity_id)
        if not workout:
            return 0

        # コメントが既にあれば振り返り不要
        if workout.get("comment"):
            return 0

        # 既にPrompt送信済みならスキップ
        if workout.get("look_back_prompted_at") is not None:
            return 0

        send_look_back_prompt(workout)
        mark_look_back_prompted(conn, workout["id"])
        conn.commit()

    logger.info("Look back prompt sent for activity %s.", summary.garmin_activity_id)
    return 1


def handle_look_back_reply(text: str, reply_token: str) -> None:
    """ユーザーの振り返りメッセージを処理してDB保存・LINE返信する。"""
    feedback = parse_look_back_message(text)

    engine = get_engine()
    with engine.connect() as conn:
        workout = get_pending_look_back_workout(conn)
        if workout:
            update_workout_look_back(
                conn,
                workout["id"],
                rpe=feedback["rpe"],
                pain=feedback["pain"],
                comment=feedback["comment"],
            )
            conn.commit()
            send_reply(reply_token, "記録しました ✅")
            logger.info("Look back saved for workout %d.", workout["id"])
        else:
            send_reply(reply_token, "紐付けるワークアウトが見つかりませんでした。")
