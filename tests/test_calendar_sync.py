from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from google.auth.exceptions import RefreshError

from run_coach.calendar import (
    EXTENDED_PROPERTY_KEY,
    EXTENDED_PROPERTY_VALUE,
    _build_event_body,
    _delete_run_coach_events,
    fetch_calendar,
    sync_plan_to_calendar,
)
from run_coach.state import (
    AgentState,
    Plan,
    UserProfile,
    RunsPerWeek,
    WorkoutPlan,
)


def _make_state(workouts: list[WorkoutPlan] | None = None) -> AgentState:
    """テスト用のAgentStateを生成する。"""
    profile = UserProfile(
        birthday=date(1990, 1, 1),
        goal="サブ4",
        runs_per_week=RunsPerWeek(min=3, max=5),
    )
    plan = None
    if workouts is not None:
        plan = Plan(
            week_start=date(2026, 3, 9),
            workout_evaluation="良好",
            workouts=workouts,
            load_summary="週3回",
            reasoning="テスト用",
        )
    return AgentState(user_profile=profile, plan=plan)


@pytest.fixture()
def sample_workouts() -> list[WorkoutPlan]:
    return [
        WorkoutPlan(
            date=date(2026, 3, 9),
            workout_type="easy_run",
            purpose="疲労抜き",
            duration_min=40,
            intensity="low",
            max_hr=140,
            notes="",
        ),
        WorkoutPlan(
            date=date(2026, 3, 10),
            workout_type="rest",
            purpose="",
            duration_min=0,
            intensity="low",
        ),
        WorkoutPlan(
            date=date(2026, 3, 11),
            workout_type="tempo",
            purpose="閾値向上",
            duration_min=50,
            intensity="high",
            max_hr=165,
            notes="4:30/kmで20分",
        ),
    ]


class TestBuildEventBody:
    def test_basic_event(self) -> None:
        workout = WorkoutPlan(
            date=date(2026, 3, 9),
            workout_type="easy_run",
            purpose="疲労抜き",
            duration_min=40,
            intensity="low",
            max_hr=140,
            notes="",
        )
        body = _build_event_body(workout)

        assert body["summary"] == "イージーラン (40min)"
        assert body["start"] == {"date": "2026-03-09"}
        assert body["end"] == {"date": "2026-03-10"}
        assert "目的: 疲労抜き" in body["description"]
        assert "強度: 低" in body["description"]
        assert "HR上限: 140" in body["description"]
        assert (
            body["extendedProperties"]["private"][EXTENDED_PROPERTY_KEY]
            == EXTENDED_PROPERTY_VALUE
        )

    def test_event_with_notes(self) -> None:
        workout = WorkoutPlan(
            date=date(2026, 3, 11),
            workout_type="tempo",
            purpose="閾値向上",
            duration_min=50,
            intensity="high",
            max_hr=165,
            notes="4:30/kmで20分",
        )
        body = _build_event_body(workout)

        assert body["summary"] == "テンポ走 (50min)"
        assert "4:30/kmで20分" in body["description"]

    def test_unknown_workout_type_uses_raw_value(self) -> None:
        workout = WorkoutPlan(
            date=date(2026, 3, 9),
            workout_type="hill_repeats",
            duration_min=30,
        )
        body = _build_event_body(workout)

        assert body["summary"] == "hill_repeats (30min)"

    def test_zero_duration(self) -> None:
        workout = WorkoutPlan(
            date=date(2026, 3, 9),
            workout_type="cross_training",
            duration_min=0,
        )
        body = _build_event_body(workout)

        assert body["summary"] == "クロストレーニング"

    def test_no_optional_fields(self) -> None:
        workout = WorkoutPlan(
            date=date(2026, 3, 9),
            workout_type="easy_run",
            intensity=None,
        )
        body = _build_event_body(workout)

        assert body["summary"] == "イージーラン"
        assert body["description"] == ""


class TestDeleteRunCoachEvents:
    def test_deletes_matching_events(self) -> None:
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.return_value = {
            "items": [
                {"id": "event1"},
                {"id": "event2"},
            ]
        }

        deleted = _delete_run_coach_events(
            mock_service, date(2026, 3, 9), date(2026, 3, 16)
        )

        assert deleted == 2
        assert mock_events.delete.call_count == 2
        mock_events.delete.assert_any_call(calendarId="primary", eventId="event1")
        mock_events.delete.assert_any_call(calendarId="primary", eventId="event2")

    def test_no_events_to_delete(self) -> None:
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.return_value = {"items": []}

        deleted = _delete_run_coach_events(
            mock_service, date(2026, 3, 9), date(2026, 3, 16)
        )

        assert deleted == 0
        mock_events.delete.assert_not_called()

    def test_uses_extended_property_filter(self) -> None:
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.return_value = {"items": []}

        _delete_run_coach_events(mock_service, date(2026, 3, 9), date(2026, 3, 16))

        mock_events.list.assert_called_once_with(
            calendarId="primary",
            timeMin="2026-03-09T00:00:00Z",
            timeMax="2026-03-16T00:00:00Z",
            privateExtendedProperty=f"{EXTENDED_PROPERTY_KEY}={EXTENDED_PROPERTY_VALUE}",
            singleEvents=True,
        )


class TestSyncPlanToCalendar:
    @patch("run_coach.calendar._get_calendar_service")
    @patch("run_coach.calendar.CLIENT_SECRET_PATH")
    def test_syncs_non_rest_workouts(
        self,
        mock_path: MagicMock,
        mock_get_service: MagicMock,
        sample_workouts: list[WorkoutPlan],
    ) -> None:
        mock_path.exists.return_value = True
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.return_value = {"items": []}

        state = _make_state(sample_workouts)
        result = sync_plan_to_calendar(state)

        assert result.plan is not None
        # rest以外の2件がinsertされること
        assert mock_events.insert.return_value.execute.call_count == 2

    @patch("run_coach.calendar._get_calendar_service")
    @patch("run_coach.calendar.CLIENT_SECRET_PATH")
    def test_skips_when_no_plan(
        self, mock_path: MagicMock, mock_get_service: MagicMock
    ) -> None:
        mock_path.exists.return_value = True
        state = _make_state(workouts=None)
        result = sync_plan_to_calendar(state)

        mock_get_service.assert_not_called()
        assert result.plan is None

    @patch("run_coach.calendar.CLIENT_SECRET_PATH")
    def test_skips_when_no_client_secret(
        self, mock_path: MagicMock, sample_workouts: list[WorkoutPlan]
    ) -> None:
        mock_path.exists.return_value = False
        state = _make_state(sample_workouts)
        result = sync_plan_to_calendar(state)

        assert result.plan is not None

    @patch("run_coach.calendar._get_calendar_service")
    @patch("run_coach.calendar.CLIENT_SECRET_PATH")
    def test_deletes_before_insert(
        self,
        mock_path: MagicMock,
        mock_get_service: MagicMock,
        sample_workouts: list[WorkoutPlan],
    ) -> None:
        mock_path.exists.return_value = True
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.return_value = {
            "items": [{"id": "old_event"}]
        }

        state = _make_state(sample_workouts)
        sync_plan_to_calendar(state)

        # deleteがinsertより先に呼ばれること
        mock_events.delete.assert_called_once_with(
            calendarId="primary", eventId="old_event"
        )
        mock_events.delete.return_value.execute.assert_called_once()

    @patch("run_coach.calendar._get_calendar_service")
    @patch("run_coach.calendar.CLIENT_SECRET_PATH")
    def test_all_rest_skips_sync(
        self, mock_path: MagicMock, mock_get_service: MagicMock
    ) -> None:
        mock_path.exists.return_value = True
        rest_only = [
            WorkoutPlan(date=date(2026, 3, 9), workout_type="rest"),
        ]
        state = _make_state(rest_only)
        result = sync_plan_to_calendar(state)

        mock_get_service.assert_not_called()
        assert result.plan is not None


@patch(
    "run_coach.calendar._get_calendar_service",
    side_effect=RefreshError("token revoked"),
)
@patch("run_coach.calendar.CLIENT_SECRET_PATH")
def test_fetch_calendar_skips_on_refresh_error(
    mock_path: MagicMock, mock_get_service: MagicMock
) -> None:
    """RefreshError発生時にfetch_calendarがクラッシュせずstateを返すこと。"""
    mock_path.exists.return_value = True
    state = _make_state()
    result = fetch_calendar(state)

    assert result.constraints.available_slots == []


@patch(
    "run_coach.calendar._get_calendar_service",
    side_effect=RefreshError("token revoked"),
)
@patch("run_coach.calendar.CLIENT_SECRET_PATH")
def test_sync_skips_on_refresh_error(
    mock_path: MagicMock,
    mock_get_service: MagicMock,
    sample_workouts: list[WorkoutPlan],
) -> None:
    """RefreshError発生時にsync_plan_to_calendarがクラッシュせずstateを返すこと。"""
    mock_path.exists.return_value = True
    state = _make_state(sample_workouts)
    result = sync_plan_to_calendar(state)

    assert result.plan is not None


@patch("run_coach.calendar.build")
@patch("run_coach.calendar.InstalledAppFlow")
@patch("run_coach.calendar.TOKEN_PATH")
@patch("run_coach.calendar.is_cloud_run", return_value=False)
def test_get_calendar_service_refresh_error_retries_auth(
    mock_is_cloud: MagicMock,
    mock_token_path: MagicMock,
    mock_flow_cls: MagicMock,
    mock_build: MagicMock,
) -> None:
    """creds.refresh()でRefreshError時にInstalledAppFlowで再認証すること。"""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "old_token"
    mock_creds.refresh.side_effect = RefreshError("token revoked")
    mock_token_path.exists.return_value = True

    mock_new_creds = MagicMock()
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_new_creds
    mock_flow_cls.from_client_secrets_file.return_value = mock_flow

    with patch(
        "run_coach.calendar.Credentials.from_authorized_user_file",
        return_value=mock_creds,
    ):
        from run_coach.calendar import _get_calendar_service

        _get_calendar_service()

    mock_flow.run_local_server.assert_called_once()
    mock_build.assert_called_once_with("calendar", "v3", credentials=mock_new_creds)
