import logging
from datetime import date
from unittest.mock import MagicMock, patch

from run_coach.line import format_plan_for_line, notify_line, send_plan_notification
from run_coach.state import (
    AgentState,
    Plan,
    RunsPerWeek,
    UserProfile,
    WorkoutPlan,
)


def _make_plan() -> Plan:
    return Plan(
        week_start=date(2026, 3, 9),
        workout_evaluation="疲労は低め。",
        workouts=[
            WorkoutPlan(
                date=date(2026, 3, 9),
                workout_type="イージーラン",
                purpose="疲労抜き",
                duration_min=40,
                intensity="low",
                max_hr=140,
                notes="リカバリージョグ",
            ),
            WorkoutPlan(
                date=date(2026, 3, 11),
                workout_type="テンポ走",
                purpose="閾値向上",
                duration_min=50,
                intensity="moderate",
                max_hr=165,
                notes="4:30/kmで20分",
            ),
        ],
        load_summary="軽めの週",
        reasoning="先週のロング走で心拍が高めだったため、今週は回復を優先。",
    )


def _make_state() -> AgentState:
    return AgentState(
        user_profile=UserProfile(
            birthday=date(1990, 1, 1),
            goal="サブ3.5",
            runs_per_week=RunsPerWeek(min=3, max=5),
        ),
    )


def test_format_plan_for_line():
    """Plan → テキスト変換。日付・曜日・メニュー・reasoning が含まれること。"""
    plan = _make_plan()
    text = format_plan_for_line(plan)

    assert "📋 1週間のトレーニング計画" in text
    assert "3/9(月) 〜 3/15(日)" in text
    assert "3/11(水)" in text
    assert "イージーラン" in text
    assert "テンポ走" in text
    assert "疲労抜き" in text
    assert "HR上限140" in text
    assert "💡" in text
    assert "先週のロング走" in text


def test_format_plan_optional_fields():
    """max_hr=None, notes='' の場合に不要な文字列が出ないこと。"""
    plan = Plan(
        week_start=date(2026, 3, 9),
        workout_evaluation="問題なし。",
        workouts=[
            WorkoutPlan(
                date=date(2026, 3, 9),
                workout_type="レスト",
                purpose="",
                duration_min=0,
                intensity="low",
                max_hr=None,
                notes="",
            ),
        ],
        load_summary="回復週",
        reasoning="",
    )
    text = format_plan_for_line(plan)

    assert "HR上限" not in text
    assert "💡" not in text
    assert "→" not in text


def test_send_notification_success(monkeypatch):
    """LINE API モック。push_message が正しいパラメータで呼ばれること。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("RUN_COACH_LINE_USER_ID", "test-user-id")

    mock_messaging_api = MagicMock()

    with patch("run_coach.line.ApiClient") as mock_api_client_cls:
        mock_api_client = MagicMock()
        mock_api_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_api_client
        )
        mock_api_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("run_coach.line.MessagingApi", return_value=mock_messaging_api):
            send_plan_notification(_make_plan())

    mock_messaging_api.push_message.assert_called_once()
    call_args = mock_messaging_api.push_message.call_args
    request = call_args[0][0]
    assert request.to == "test-user-id"
    assert len(request.messages) == 1


def test_send_notification_no_token(monkeypatch, caplog):
    """環境変数未設定時に例外なくスキップ、警告ログ出力。"""
    monkeypatch.delenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RUN_COACH_LINE_USER_ID", raising=False)

    with caplog.at_level(logging.WARNING):
        send_plan_notification(_make_plan())

    assert "Skipping LINE notification" in caplog.text


def test_send_notification_api_error(monkeypatch, caplog):
    """API例外時にキャッチされてパイプライン継続。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("RUN_COACH_LINE_USER_ID", "test-user-id")

    with patch("run_coach.line.ApiClient") as mock_api_client_cls:
        mock_api_client = MagicMock()
        mock_api_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_api_client
        )
        mock_api_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("run_coach.line.MessagingApi") as mock_messaging_api_cls:
            mock_messaging_api_cls.return_value.push_message.side_effect = Exception(
                "API Error"
            )

            with caplog.at_level(logging.ERROR):
                send_plan_notification(_make_plan())

    assert "Failed to send LINE notification" in caplog.text


def test_notify_line_node(monkeypatch):
    """LangGraph ノードとして state を受け取り返すこと。"""
    monkeypatch.delenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RUN_COACH_LINE_USER_ID", raising=False)

    state = _make_state()
    state.plan = _make_plan()

    result = notify_line(state)

    assert result is state
    assert result.plan is not None
