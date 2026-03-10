"""ワークアウト保存のLangGraphノード。"""

from __future__ import annotations

import logging

from run_coach.converters import pace_str_to_seconds
from run_coach.database import (
    get_engine,
    save_splits,
    upsert_workouts,
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
    """ワークアウトをPostgreSQLにupsertで保存する。

    descriptionがあればパースしてrpe/pain/commentも一緒に保存する。
    garmin_activity_idが既存の場合はGarmin側の変更を反映する。
    """
    workouts = state.signals.recent_workouts
    if not workouts:
        return state

    engine = get_engine()
    with engine.connect() as conn:
        workouts_with_id = [w for w in workouts if w.garmin_activity_id]

        workout_dicts = []
        for workout in workouts_with_id:
            description = workout.description or ""
            feedback = parse_description(description)
            workout_dicts.append(
                {
                    "garmin_activity_id": workout.garmin_activity_id,
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
            )

        id_map = upsert_workouts(conn, workout_dicts)

        splits_count = 0
        for activity_id, workout_id in id_map.items():
            splits_count += _save_activity_splits(conn, workout_id, activity_id)

        conn.commit()
        print(f"  DB: {len(id_map)}件upsert ({splits_count}ラップ)")

    return state
