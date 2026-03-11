from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request  # type: ignore[import-untyped]
from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import Resource, build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from run_coach.cloud import is_cloud_run
from run_coach.state import AgentState, CalendarSlot, WorkoutPlan

logger = logging.getLogger(__name__)

CALENDAR_LOOKAHEAD_DAYS = 7
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
RUN_COACH_DIR = Path.home() / ".run-coach"
TOKEN_PATH = RUN_COACH_DIR / "token.json"
CLIENT_SECRET_PATH = RUN_COACH_DIR / "client_secret.json"


def _get_calendar_id() -> str:
    return os.environ.get("GOOGLE_CALENDAR_ID", "primary")


def _get_calendar_service() -> Resource:
    """Authenticate and return a Google Calendar API service object."""
    if is_cloud_run():
        import google.auth  # type: ignore[import-untyped]

        creds, _ = google.auth.default(scopes=SCOPES)
        return build("calendar", "v3", credentials=creds)

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _fetch_events(service) -> dict[date, list[str]]:
    """Fetch calendar events for the next 7 days."""
    now = datetime.now(tz=timezone.utc)
    time_max = now + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)

    events_result = (
        service.events()
        .list(
            calendarId=_get_calendar_id(),
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events_by_date: dict[date, list[str]] = {}
    for event in events_result.get("items", []):
        summary = event.get("summary", "(無題)")
        start_dt = event["start"].get("dateTime")
        if start_dt:
            event_date = date.fromisoformat(start_dt[:10])
            start_time = datetime.fromisoformat(start_dt).strftime("%H:%M")
            end_dt = event["end"].get("dateTime", "")
            end_time = (
                datetime.fromisoformat(end_dt).strftime("%H:%M") if end_dt else ""
            )
            label = (
                f"{start_time}-{end_time} {summary}"
                if end_time
                else f"{start_time} {summary}"
            )
        else:
            start_date_str = event["start"].get("date", "")
            event_date = date.fromisoformat(start_date_str)
            label = f"終日: {summary}"
        events_by_date.setdefault(event_date, []).append(label)

    return events_by_date


def _build_slots(events_by_date: dict[date, list[str]]) -> list[CalendarSlot]:
    """Build 7 days of CalendarSlots from events."""
    today = date.today()
    slots: list[CalendarSlot] = []
    for i in range(CALENDAR_LOOKAHEAD_DAYS):
        d = today + timedelta(days=i)
        events = events_by_date.get(d, [])
        slots.append(CalendarSlot(date=d, available=len(events) == 0, events=events))
    return slots


def fetch_calendar(state: AgentState) -> AgentState:
    """Fetch Google Calendar events and populate state.constraints.available_slots."""
    print("カレンダーを取得中...")
    if not is_cloud_run() and not CLIENT_SECRET_PATH.exists():
        logger.info("client_secret.jsonが未配置のためカレンダー取得をスキップします")
        return state

    try:
        service = _get_calendar_service()
        events_by_date = _fetch_events(service)
        state.constraints.available_slots = _build_slots(events_by_date)
    except (HttpError, OSError, ValueError):
        logger.warning("カレンダーの取得に失敗しました", exc_info=True)

    print(f"  {len(state.constraints.available_slots)} 日分のスロットを取得しました")
    return state


# ---------------------------------------------------------------------------
# Phase 3.5: プランをGoogle Calendarに同期
# ---------------------------------------------------------------------------

EXTENDED_PROPERTY_KEY = "created_by"
EXTENDED_PROPERTY_VALUE = "run-coach"

WORKOUT_TYPE_LABEL: dict[str, str] = {
    "easy_run": "イージーラン",
    "tempo": "テンポ走",
    "intervals": "インターバル",
    "long_run": "ロング走",
    "rest": "休息",
    "cross_training": "クロストレーニング",
}

INTENSITY_LABEL: dict[str, str] = {
    "low": "低",
    "moderate": "中",
    "high": "高",
}


def _delete_run_coach_events(service: Resource, time_min: date, time_max: date) -> int:
    """対象期間内のrun-coachが作成したイベントを削除する。削除件数を返す。"""
    events_result = (
        service.events()
        .list(
            calendarId=_get_calendar_id(),
            timeMin=f"{time_min}T00:00:00Z",
            timeMax=f"{time_max}T00:00:00Z",
            privateExtendedProperty=f"{EXTENDED_PROPERTY_KEY}={EXTENDED_PROPERTY_VALUE}",
            singleEvents=True,
        )
        .execute()
    )

    deleted_count = 0
    for event in events_result.get("items", []):
        service.events().delete(
            calendarId=_get_calendar_id(), eventId=event["id"]
        ).execute()
        deleted_count += 1

    return deleted_count


def _build_event_body(workout: WorkoutPlan) -> dict:
    """WorkoutPlanからGoogle Calendar APIのイベントボディを構築する。"""
    workout_label = WORKOUT_TYPE_LABEL.get(workout.workout_type, workout.workout_type)
    duration = workout.duration_min or 0
    summary = f"{workout_label} ({duration}min)" if duration else workout_label

    description_parts: list[str] = []
    if workout.purpose:
        description_parts.append(f"目的: {workout.purpose}")
    if workout.intensity:
        intensity_label = INTENSITY_LABEL.get(workout.intensity, workout.intensity)
        description_parts.append(f"強度: {intensity_label}")
    if workout.max_hr:
        description_parts.append(f"HR上限: {workout.max_hr}")
    if workout.notes:
        description_parts.append(workout.notes)

    end_date = workout.date + timedelta(days=1)

    return {
        "summary": summary,
        "start": {"date": str(workout.date)},
        "end": {"date": str(end_date)},
        "description": "\n".join(description_parts),
        "extendedProperties": {
            "private": {EXTENDED_PROPERTY_KEY: EXTENDED_PROPERTY_VALUE}
        },
    }


def _create_workout_event(service: Resource, workout: WorkoutPlan) -> None:
    """WorkoutPlanをGoogle Calendarにイベントとして作成する。"""
    body = _build_event_body(workout)
    service.events().insert(calendarId=_get_calendar_id(), body=body).execute()


def sync_plan_to_calendar(state: AgentState) -> AgentState:
    """LangGraphノード: プランのワークアウトをGoogle Calendarに同期する。"""
    if not state.plan:
        return state

    print("カレンダーにプランを同期中...")

    if not is_cloud_run() and not CLIENT_SECRET_PATH.exists():
        logger.info("client_secret.jsonが未配置のためカレンダー同期をスキップします")
        return state

    workouts_to_sync = [w for w in state.plan.workouts if w.workout_type != "rest"]
    if not workouts_to_sync:
        print("  同期対象のワークアウトがありません")
        return state

    try:
        service = _get_calendar_service()

        time_min = state.plan.week_start
        time_max = max(w.date for w in state.plan.workouts) + timedelta(days=1)
        deleted_count = _delete_run_coach_events(service, time_min, time_max)
        if deleted_count:
            print(f"  既存のイベント {deleted_count} 件を削除しました")

        for workout in workouts_to_sync:
            _create_workout_event(service, workout)

        print(f"  {len(workouts_to_sync)} 件のワークアウトをカレンダーに登録しました")
    except (HttpError, OSError, ValueError):
        logger.warning("カレンダーへの同期に失敗しました", exc_info=True)

    return state
