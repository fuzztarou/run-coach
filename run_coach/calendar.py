from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request  # type: ignore[import-untyped]
from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import Resource, build  # type: ignore[import-untyped]

from run_coach.state import AgentState, CalendarSlot

logger = logging.getLogger(__name__)

CALENDAR_LOOKAHEAD_DAYS = 7
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
RUN_COACH_DIR = Path.home() / ".run-coach"
TOKEN_PATH = RUN_COACH_DIR / "token.json"
CLIENT_SECRET_PATH = RUN_COACH_DIR / "client_secret.json"


def _get_calendar_service() -> Resource:
    """Authenticate and return a Google Calendar API service object."""
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
            calendarId="primary",
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
    if not CLIENT_SECRET_PATH.exists():
        logger.info("client_secret.jsonが未配置のためカレンダー取得をスキップします")
        return state

    try:
        service = _get_calendar_service()
        events_by_date = _fetch_events(service)
        state.constraints.available_slots = _build_slots(events_by_date)
    except Exception:
        logger.warning("カレンダーの取得に失敗しました", exc_info=True)

    return state
