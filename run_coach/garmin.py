from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin

from run_coach.state import AgentState, RaceEvent, Signals, WorkoutSummary

logger = logging.getLogger(__name__)

# トークン保存先
TOKENSTORE = str(Path.home() / ".garminconnect")
# 一度に取得するアクティビティの最大件数
ACTIVITY_FETCH_LIMIT = 10
# ワークアウト履歴の取得対象期間（日数）
LOOKBACK_DAYS = 14
# 大会情報のスキャン対象期間（月数）
RACE_SCAN_MONTHS = 12
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


# fetch_workouts / fetch_races で共有するクライアントキャッシュ。
# _login() を複数回呼んでも実際のログインは初回のみ。
_garmin_client: Garmin | None = None


def _login() -> Garmin:
    """Login to Garmin Connect. Uses saved tokens if available, otherwise credentials."""
    global _garmin_client
    if _garmin_client is not None:
        return _garmin_client

    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    client = Garmin(email=email, password=password)
    try:
        client.login(tokenstore=TOKENSTORE)
    except FileNotFoundError:
        client.login()
        client.garth.dump(TOKENSTORE)

    _garmin_client = client
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


def fetch_workouts(state: AgentState) -> AgentState:
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


def _fetch_race_detail(client: Garmin, event_id: int) -> RaceEvent | None:
    """Fetch race event detail from Garmin Calendar API."""
    try:
        event_detail = client.garth.connectapi(f"/calendar-service/event/{event_id}")
        event_name = event_detail.get("eventName", event_detail.get("title", "Unknown"))
        event_date_str = event_detail.get("date", "")
        if not event_date_str:
            return None
        event_date = date.fromisoformat(event_date_str[:10])
        distance_m = event_detail.get("distance")
        distance_km = round(distance_m / 1000, 2) if distance_m else None
        goal_time = event_detail.get("goalTimeInSeconds")
        location = event_detail.get("location")
        return RaceEvent(
            event_name=event_name,
            date=event_date,
            distance_km=distance_km,
            goal_time_seconds=goal_time,
            location=location,
        )
    except Exception:
        logger.warning("レース詳細の取得に失敗: event_id=%s", event_id, exc_info=True)
        return None


def fetch_races(state: AgentState) -> AgentState:
    """Fetch upcoming race events from Garmin Calendar and populate state.constraints.races."""
    try:
        client = _login()
    except Exception:
        logger.warning(
            "Garminログインに失敗したため大会情報をスキップします", exc_info=True
        )
        return state

    today = date.today()
    races: list[RaceEvent] = []

    for month_offset in range(RACE_SCAN_MONTHS):
        target_month = today.month + month_offset
        target_year = today.year
        if target_month > 12:
            target_month -= 12
            target_year += 1

        try:
            # Garmin Calendar APIの月インデックス: 0始まり
            monthly_calendar = client.garth.connectapi(
                f"/calendar-service/year/{target_year}/month/{target_month - 1}",
            )
        except Exception as e:
            logger.warning(
                "カレンダー取得失敗: %d/%d (%s)", target_year, target_month, e
            )
            continue

        for item in monthly_calendar.get("calendarItems", []):
            if item.get("itemType") != "event" or not item.get("isRace"):
                continue
            event_id = item.get("id")
            if not event_id:
                continue
            race = _fetch_race_detail(client, event_id)
            if race:
                races.append(race)

    if races:
        # 最も近い大会をprimaryに
        races.sort(key=lambda r: r.date)
        races[0].is_primary = True

    state.constraints.races = races
    return state
