from datetime import date

from run_coach.state import RaceEvent


def test_race_event_full():
    """フルフィールドのRaceEventが正しく生成できること"""
    r = RaceEvent(
        event_name="東京マラソン",
        date=date(2026, 3, 1),
        distance_km=42.195,
        goal_time_seconds=14400.0,
        location="東京",
        is_primary=True,
    )
    assert r.event_name == "東京マラソン"
    assert r.distance_km == 42.195
    assert r.goal_time_seconds == 14400.0
    assert r.is_primary is True


def test_race_event_minimal():
    """最小フィールドのRaceEventが正しく生成できること"""
    r = RaceEvent(event_name="ローカル10K", date=date(2026, 5, 15))
    assert r.distance_km is None
    assert r.goal_time_seconds is None
    assert r.location is None
    assert r.is_primary is False
