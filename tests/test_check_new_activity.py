"""POST /internal/check-new-activity のテスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_garmin_activity(activity_id: str, distance: float = 5000) -> dict:
    return {
        "activityId": activity_id,
        "activityType": {"typeKey": "running"},
        "distance": distance,
        "duration": 1800,
        "startTimeLocal": "2026-03-12 07:00:00",
        "averageHR": 145,
        "aerobicTrainingEffect": 3.0,
        "description": "",
    }


def _mock_workout(**overrides) -> dict:
    base = {
        "id": 1,
        "garmin_activity_id": "ACT001",
        "date": date(2026, 3, 12),
        "workout_type": "running",
        "distance_km": 5.0,
        "duration_min": 30.0,
        "comment": None,
        "look_back_prompted_at": None,
    }
    base.update(overrides)
    return base


@patch("run_coach.api.check_connection")
@patch("run_coach.look_back._login")
def test_check_new_activity_sends_prompt(mock_login, _mock_conn, monkeypatch):
    """新着アクティビティに対して振り返りPromptが送信されること。"""
    mock_client = MagicMock()
    mock_client.get_activities.return_value = [_make_garmin_activity("ACT001")]
    mock_login.return_value = mock_client

    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("RUN_COACH_LINE_USER_ID", "test-user")

    workout = _mock_workout()

    with (
        patch("run_coach.look_back.get_engine") as mock_engine,
        patch("run_coach.look_back.send_look_back_prompt") as mock_send,
        patch("run_coach.look_back.upsert_workouts"),
        patch("run_coach.look_back.get_workout_by_garmin_id", return_value=workout),
        patch("run_coach.look_back.mark_look_back_prompted"),
    ):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from run_coach.api import app

        client = TestClient(app)
        response = client.post("/internal/check-new-activity")

    assert response.status_code == 200
    assert response.json() == {"prompted": 1}
    mock_send.assert_called_once_with(workout)


@patch("run_coach.api.check_connection")
@patch("run_coach.look_back._login")
def test_check_new_activity_skips_when_comment_exists(
    mock_login, _mock_conn, monkeypatch
):
    """コメントが既にある場合は通知しないこと。"""
    mock_client = MagicMock()
    mock_client.get_activities.return_value = [_make_garmin_activity("ACT001")]
    mock_login.return_value = mock_client

    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("RUN_COACH_LINE_USER_ID", "test-user")

    workout = _mock_workout(comment="調子良かった")

    with (
        patch("run_coach.look_back.get_engine") as mock_engine,
        patch("run_coach.look_back.send_look_back_prompt") as mock_send,
        patch("run_coach.look_back.upsert_workouts"),
        patch("run_coach.look_back.get_workout_by_garmin_id", return_value=workout),
    ):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from run_coach.api import app

        client = TestClient(app)
        response = client.post("/internal/check-new-activity")

    assert response.status_code == 200
    assert response.json() == {"prompted": 0}
    mock_send.assert_not_called()


@patch("run_coach.api.check_connection")
@patch("run_coach.look_back._login")
def test_check_new_activity_skips_already_prompted(mock_login, _mock_conn, monkeypatch):
    """既にPrompt送信済みの場合はスキップすること。"""
    mock_client = MagicMock()
    mock_client.get_activities.return_value = [_make_garmin_activity("ACT001")]
    mock_login.return_value = mock_client

    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("RUN_COACH_LINE_USER_ID", "test-user")

    from datetime import datetime, timezone

    workout = _mock_workout(look_back_prompted_at=datetime.now(timezone.utc))

    with (
        patch("run_coach.look_back.get_engine") as mock_engine,
        patch("run_coach.look_back.send_look_back_prompt") as mock_send,
        patch("run_coach.look_back.upsert_workouts"),
        patch("run_coach.look_back.get_workout_by_garmin_id", return_value=workout),
    ):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from run_coach.api import app

        client = TestClient(app)
        response = client.post("/internal/check-new-activity")

    assert response.status_code == 200
    assert response.json() == {"prompted": 0}
    mock_send.assert_not_called()


@patch("run_coach.api.check_connection")
@patch("run_coach.look_back._login")
def test_check_new_activity_no_activities(mock_login, _mock_conn):
    """アクティビティなしの場合 prompted=0 を返すこと。"""
    mock_client = MagicMock()
    mock_client.get_activities.return_value = []
    mock_login.return_value = mock_client

    from run_coach.api import app

    client = TestClient(app)
    response = client.post("/internal/check-new-activity")

    assert response.status_code == 200
    assert response.json() == {"prompted": 0}


@patch("run_coach.api.check_connection")
@patch("run_coach.look_back._login")
def test_check_new_activity_skips_non_running(mock_login, _mock_conn):
    """ランニング以外のアクティビティはスキップされること。"""
    mock_client = MagicMock()
    mock_client.get_activities.return_value = [
        {
            "activityId": "SWIM001",
            "activityType": {"typeKey": "swimming"},
            "distance": 2000,
            "duration": 1800,
            "startTimeLocal": "2026-03-12 07:00:00",
        }
    ]
    mock_login.return_value = mock_client

    from run_coach.api import app

    client = TestClient(app)
    response = client.post("/internal/check-new-activity")

    assert response.status_code == 200
    assert response.json() == {"prompted": 0}
