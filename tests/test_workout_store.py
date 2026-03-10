"""save_workouts() LangGraphノードの回帰テスト。"""

from datetime import date

from sqlalchemy import text

from run_coach.database import get_engine
from run_coach.state import (
    AgentState,
    RunsPerWeek,
    Signals,
    UserProfile,
    WorkoutSummary,
)
from run_coach.workout_store import save_workouts


def _mock_splits(activity_id: str) -> list[dict]:
    """Garmin API のモック。"""
    return [
        {
            "split_number": 1,
            "distance_km": 1.0,
            "duration_sec": 300.0,
            "avg_pace": "5:00",
            "avg_hr": 145,
            "max_hr": 155,
            "elevation_gain": 5.0,
        },
        {
            "split_number": 2,
            "distance_km": 1.0,
            "duration_sec": 310.0,
            "avg_pace": "5:10",
            "avg_hr": 150,
            "max_hr": 160,
            "elevation_gain": 3.0,
        },
    ]


def _make_profile() -> UserProfile:
    return UserProfile(
        birthday=date(1996, 1, 1),
        goal="サブ3.5",
        runs_per_week=RunsPerWeek(min=3, max=5),
    )


def _make_state(*activity_ids: str) -> AgentState:
    workouts = [
        WorkoutSummary(
            date=date(2026, 3, 1),
            type="running",
            distance_km=10.0,
            duration_min=55.0,
            avg_pace="5:30",
            avg_hr=150,
            training_effect=3.2,
            garmin_activity_id=aid,
            description="RPE:7 調子良かった",
        )
        for aid in activity_ids
    ]
    return AgentState(
        user_profile=_make_profile(),
        signals=Signals(recent_workouts=workouts),
    )


def test_save_workouts_node(monkeypatch, clean_db):
    """save_workouts LangGraphノードがDB保存を正しく行うことを確認。"""
    monkeypatch.setattr("run_coach.workout_store.fetch_activity_splits", _mock_splits)

    state = _make_state("ACT001", "ACT002")
    result = save_workouts(state)

    # stateがそのまま返されること
    assert result.signals.recent_workouts == state.signals.recent_workouts

    # DBに保存されていること
    engine = get_engine()
    with engine.connect() as conn:
        workout_rows = conn.execute(
            text("SELECT garmin_activity_id FROM workouts ORDER BY garmin_activity_id")
        ).fetchall()
        assert [r[0] for r in workout_rows] == ["ACT001", "ACT002"]

        split_count = conn.execute(
            text("SELECT count(*) FROM workout_splits")
        ).fetchone()
        assert split_count is not None
        assert split_count[0] == 4  # 2ワークアウト × 2ラップ


def test_save_workouts_upsert_no_duplicate(monkeypatch, clean_db):
    """同一ワークアウトを2回保存してもレコード数は1件のままであること。"""
    monkeypatch.setattr("run_coach.workout_store.fetch_activity_splits", _mock_splits)

    state = _make_state("ACT001")
    save_workouts(state)
    save_workouts(state)  # 2回目（upsert）

    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM workouts")).fetchone()
        assert count is not None
        assert count[0] == 1
