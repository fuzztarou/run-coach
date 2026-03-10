"""ワークアウト保存のLangGraphノード。"""

from __future__ import annotations

import logging

from run_coach.converters import pace_str_to_seconds
from run_coach.database import (
    get_connection,
    get_unsaved_activity_ids,
    save_splits,
    save_workout,
)
from run_coach.feedback_parser import parse_description
from run_coach.garmin import fetch_activity_splits
from run_coach.state import AgentState

logger = logging.getLogger(__name__)


def _save_activity_splits(conn, workout_id: int, activity_id: str) -> int:
    """ラップデータをGarminから取得して保存する。保存ラップ数を返す。"""
    splits = fetch_activity_splits(activity_id)
    if not splits:
        return 0
    save_splits(conn, workout_id, splits)
    return len(splits)


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
        splits_count = 0
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
                "pace_seconds_per_km": pace_str_to_seconds(workout.avg_pace),
                "avg_heart_rate_bpm": workout.avg_hr,
                "training_effect": workout.training_effect,
                "description": description,
                "rpe": feedback["rpe"],
                "pain": feedback["pain"],
                "comment": feedback["comment"],
            }
            workout_id = save_workout(conn, workout_dict)
            if workout_id is None:
                continue
            saved_count += 1
            splits_count += _save_activity_splits(conn, workout_id, activity_id)

        print(f"  SQLite: {saved_count}件保存 ({splits_count}ラップ)")
    finally:
        conn.close()

    return state
