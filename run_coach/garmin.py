from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin

from run_coach.state import AgentState, Signals, WorkoutSummary

# トークン保存先
TOKENSTORE = str(Path.home() / ".garminconnect")
# 一度に取得するアクティビティの最大件数
ACTIVITY_FETCH_LIMIT = 10
# ワークアウト履歴の取得対象期間（日数）
LOOKBACK_DAYS = 14
# 取得対象のアクティビティタイプ
TARGET_ACTIVITY_TYPES = (
    "running",
    "track_running",
    "trail_running",
    "treadmill_running",
    "walking",
    "casual_walking",
    "speed_walking",
)


def _login() -> Garmin:
    """Login to Garmin Connect. Uses saved tokens if available, otherwise credentials."""
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    client = Garmin(email=email, password=password)
    try:
        client.login(tokenstore=TOKENSTORE)
    except FileNotFoundError:
        client.login()
        client.garth.dump(TOKENSTORE)
    return client


def summarize_activity(activity: dict) -> WorkoutSummary | None:
    """Convert a raw Garmin activity dict into a WorkoutSummary."""
    activity_type = activity.get("activityType", {}).get("typeKey", "unknown")
    if activity_type not in TARGET_ACTIVITY_TYPES:
        return None

    distance_m = activity.get("distance", 0) or 0
    duration_s = activity.get("duration", 0) or 0
    distance_km = distance_m / 1000
    duration_min = duration_s / 60

    if distance_km > 0:
        pace_s_per_km = duration_s / distance_km
        pace_min = int(pace_s_per_km // 60)
        pace_sec = int(pace_s_per_km % 60)
        avg_pace = f"{pace_min}:{pace_sec:02d}"
    else:
        avg_pace = "0:00"

    start_local = activity.get("startTimeLocal", "")
    activity_date = (
        date.fromisoformat(start_local[:10]) if start_local else date.today()
    )

    return WorkoutSummary(
        date=activity_date,
        type=activity_type,
        distance_km=round(distance_km, 2),
        duration_min=round(duration_min, 1),
        avg_pace=avg_pace,
        avg_hr=activity.get("averageHR"),
        training_effect=activity.get("aerobicTrainingEffect"),
    )


def fetch_garmin(state: AgentState) -> AgentState:
    """Fetch recent workouts from Garmin Connect and populate state.signals."""
    client = _login()

    activities = client.get_activities(start=0, limit=ACTIVITY_FETCH_LIMIT)

    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    workouts: list[WorkoutSummary] = []
    for act in activities:
        summary = summarize_activity(act)
        if summary and summary.date >= cutoff:
            workouts.append(summary)

    race_predictions = None
    try:
        raw_predictions = client.get_race_predictions()
        if raw_predictions:
            race_predictions = {k: str(v) for k, v in raw_predictions.items() if v}
    except Exception:
        pass

    state.signals = Signals(
        recent_workouts=sorted(workouts, key=lambda w: w.date),
        race_predictions=race_predictions,
    )
    return state
