from run_coach.garmin import summarize_activity


def _make_activity(**overrides) -> dict:
    """Create a mock Garmin activity dict."""
    base = {
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2026-03-01 08:00:00",
        "distance": 10000.0,  # 10km in meters
        "duration": 3300.0,  # 55min in seconds
        "averageHR": 150,
        "aerobicTrainingEffect": 3.2,
    }
    base.update(overrides)
    return base


def test_summarize_running_activity():
    """距離・ペース・心拍の変換が正しいこと"""
    result = summarize_activity(_make_activity())
    assert result is not None
    assert result.distance_km == 10.0
    assert result.duration_min == 55.0
    assert result.avg_pace == "5:30"
    assert result.avg_hr == 150


def test_summarize_non_target_returns_none():
    """対象外のアクティビティはNoneを返すこと"""
    assert (
        summarize_activity(_make_activity(activityType={"typeKey": "cycling"})) is None
    )


def test_summarize_zero_distance():
    """距離0でゼロ除算しないこと"""
    result = summarize_activity(_make_activity(distance=0))
    assert result is not None
    assert result.avg_pace == "0:00"
