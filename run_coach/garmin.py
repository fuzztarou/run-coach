from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError  # type: ignore[import-untyped]

from run_coach.cloud import is_cloud_run
from run_coach.converters import pace_seconds_to_str
from run_coach.state import AgentState, RaceEvent, Signals, WorkoutSummary

logger = logging.getLogger(__name__)

# トークン保存先（Cloud Runでは /tmp 配下を使用）
GARMIN_TOKENSTORE_LOCAL = str(Path.home() / ".garminconnect")
GARMIN_TOKENSTORE_CLOUD = "/tmp/.garminconnect"
GCS_GARMIN_TOKEN_PREFIX = "garmin-tokens"
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
# GCSバケット名（prefetch_tokens で設定される）
_gcs_bucket: str = ""


def _get_tokenstore() -> str:
    """環境に応じたトークン保存先パスを返す。"""
    return GARMIN_TOKENSTORE_CLOUD if is_cloud_run() else GARMIN_TOKENSTORE_LOCAL


def prefetch_tokens() -> None:
    """GCSからGarminトークンをダウンロードする。Cloud Run起動時に呼ぶ。"""
    global _gcs_bucket
    bucket = os.environ.get("RUN_COACH_GCS_BUCKET", "")
    if not bucket:
        return
    _gcs_bucket = bucket
    from run_coach.gcs import download_directory

    tokenstore = _get_tokenstore()
    download_directory(bucket, GCS_GARMIN_TOKEN_PREFIX, tokenstore)


def _upload_tokens_to_gcs() -> None:
    """認証後のトークンをGCSに書き戻す。"""
    if not _gcs_bucket:
        return
    from run_coach.gcs import upload_directory

    tokenstore = _get_tokenstore()
    upload_directory(_gcs_bucket, tokenstore, GCS_GARMIN_TOKEN_PREFIX)


def _login() -> Garmin:
    """Login to Garmin Connect. Uses saved tokens if available, otherwise credentials."""
    global _garmin_client
    if _garmin_client is not None:
        return _garmin_client

    tokenstore = _get_tokenstore()
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    client = Garmin(email=email, password=password)
    try:
        client.login(tokenstore=tokenstore)
    except (FileNotFoundError, GarminConnectAuthenticationError):
        logger.info("トークンが無効または未保存のため、クレデンシャルでログインします")
        client.login()

    # リフレッシュ済みトークンを含め毎回保存（次回セッションで再利用）
    client.garth.dump(tokenstore)

    # Cloud RunではGCSにも書き戻す
    if is_cloud_run():
        _upload_tokens_to_gcs()

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
        training_effect=round(activity["aerobicTrainingEffect"], 2)
        if activity.get("aerobicTrainingEffect")
        else None,
        garmin_activity_id=str(activity.get("activityId", "")),
        description=activity.get("description", ""),
    )


def parse_splits(raw_splits: dict) -> list[dict]:
    """Garmin splits APIレスポンスをパースし、ラップデータのリストに変換する。

    Args:
        raw_splits: client.get_activity_splits() の戻り値

    Returns:
        ラップごとの辞書リスト。各辞書は split_number, distance_km,
        duration_sec, avg_pace, avg_hr, max_hr, elevation_gain を含む。
    """
    laps = raw_splits.get("lapDTOs", [])
    result: list[dict] = []
    for lap in laps:
        distance_m = lap.get("distance", 0) or 0
        duration_sec = lap.get("duration", 0) or 0
        distance_km = round(distance_m / 1000, 3)
        avg_pace = pace_seconds_to_str(duration_sec, distance_km)

        result.append(
            {
                "split_number": lap.get("lapIndex", len(result) + 1),
                "distance_km": distance_km,
                "duration_sec": round(duration_sec, 1),
                "avg_pace": avg_pace,
                "avg_hr": int(lap["averageHR"]) if lap.get("averageHR") else None,
                "max_hr": int(lap["maxHR"]) if lap.get("maxHR") else None,
                "elevation_gain": lap.get("elevationGain"),
            }
        )
    return result


def fetch_activity_splits(activity_id: str) -> list[dict]:
    """Garmin ConnectからアクティビティのラップデータをAPI取得してパースする。"""
    client = _login()
    try:
        raw_splits = client.get_activity_splits(activity_id)
        if not isinstance(raw_splits, dict):
            return []
        return parse_splits(raw_splits)
    except (KeyError, TypeError, OSError):
        logger.warning(
            "ラップデータの取得に失敗: activity_id=%s", activity_id, exc_info=True
        )
        return []


def write_description_to_garmin(garmin_activity_id: str, description: str) -> None:
    """Garmin アクティビティの description を更新する。"""
    client = _login()
    client.garth.connectapi(
        f"/activity-service/activity/{garmin_activity_id}",
        method="PUT",
        json={"activityId": garmin_activity_id, "description": description},
    )


def fetch_workouts(state: AgentState) -> AgentState:
    """Fetch recent workouts from Garmin Connect and populate state.signals."""
    print("Garmin Connect からデータを取得中...")
    client = _login()

    # get_activities() の戻り値は dict | list なので型を絞り込む
    raw_activities = client.get_activities(start=0, limit=ACTIVITY_FETCH_LIMIT)
    activities: list[dict] = raw_activities if isinstance(raw_activities, list) else []

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
    except (KeyError, TypeError, AttributeError):
        pass

    state.signals = Signals(
        recent_workouts=sorted(workouts, key=lambda w: w.date),
        race_predictions=race_predictions,
    )
    print(f"  {len(state.signals.recent_workouts)} 件のワークアウトを取得しました")
    return state


def _fetch_race_detail(client: Garmin, event_id: int) -> RaceEvent | None:
    """Fetch race event detail from Garmin Calendar API."""
    try:
        # connectapi() の戻り値は dict | list | None なので型を絞り込む
        raw = client.garth.connectapi(f"/calendar-service/event/{event_id}")
        if not isinstance(raw, dict):
            return None
        event_detail: dict = raw
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
    except (KeyError, TypeError, ValueError, OSError):
        logger.warning("レース詳細の取得に失敗: event_id=%s", event_id, exc_info=True)
        return None


def fetch_races(state: AgentState) -> AgentState:
    """Fetch upcoming race events from Garmin Calendar and populate state.constraints.races."""
    print("大会情報を取得中...")
    try:
        client = _login()
    except (GarminConnectAuthenticationError, OSError):
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
            raw_calendar = client.garth.connectapi(
                f"/calendar-service/year/{target_year}/month/{target_month - 1}",
            )
        except (KeyError, TypeError, OSError) as e:
            logger.warning(
                "カレンダー取得失敗: %d/%d (%s)", target_year, target_month, e
            )
            continue

        # connectapi() の戻り値は dict | list | None なので型を絞り込む
        if not isinstance(raw_calendar, dict):
            continue
        monthly_calendar: dict = raw_calendar
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
    print(f"  {len(state.constraints.races)} 件の大会を取得しました")
    return state
