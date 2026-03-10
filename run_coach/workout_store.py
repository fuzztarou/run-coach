"""ワークアウト保存のLangGraphノード。"""

from __future__ import annotations

import logging

from run_coach.database import (
    get_connection,
    get_unsaved_activity_ids,
    save_workout,
)
from run_coach.feedback_parser import parse_description
from run_coach.state import AgentState

logger = logging.getLogger(__name__)


def _pace_str_to_seconds(pace: str) -> float:
    """ペース文字列 "5:30" を秒/km (330.0) に変換する。"""
    parts = pace.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def save_workouts(state: AgentState) -> AgentState:
    """ワークアウトをSQLiteに保存する。

    descriptionがあればパースしてrpe/pain/commentも一緒に保存する。
    garmin_activity_idが重複する場合はスキップ（INSERT OR IGNORE）。
    """
    workouts = state.signals.recent_workouts
    if not workouts:
        return state

    conn = get_connection()
    try:
        workouts_with_id = [w for w in workouts if w.garmin_activity_id]

        all_ids = [
            w.garmin_activity_id for w in workouts_with_id if w.garmin_activity_id
        ]
        unsaved_ids = set(get_unsaved_activity_ids(conn, all_ids))

        saved_count = 0
        for workout in workouts_with_id:
            activity_id = workout.garmin_activity_id
            assert activity_id is not None  # workouts_with_idでフィルタ済み

            if activity_id not in unsaved_ids:
                continue

            description = workout.description or ""
            feedback = parse_description(description)

            workout_dict = {
                "garmin_activity_id": activity_id,
                "date": workout.date,
                "workout_type": workout.type,
                "distance_km": workout.distance_km,
                "duration_min": workout.duration_min,
                "pace_seconds_per_km": _pace_str_to_seconds(workout.avg_pace),
                "avg_heart_rate_bpm": workout.avg_hr,
                "training_effect": workout.training_effect,
                "description": description,
                "rpe": feedback["rpe"],
                "pain": feedback["pain"],
                "comment": feedback["comment"],
            }
            save_workout(conn, workout_dict)
            saved_count += 1

        print(f"  SQLite: {saved_count}件保存")
    finally:
        conn.close()

    return state
