from run_coach.garmin import parse_splits, summarize_activity


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


# --- parse_splits テスト ---


def _make_raw_splits(*laps) -> dict:
    """Garmin splits APIレスポンスのモックを生成する。"""
    return {"activityId": 12345, "lapDTOs": list(laps)}


def _make_lap(**overrides) -> dict:
    """ラップデータのモックを生成する。"""
    base = {
        "distance": 1000.0,  # 1km in meters
        "duration": 330.0,  # 5:30 in seconds
        "elevationGain": 5.0,
        "averageHR": 145.0,
        "maxHR": 160.0,
        "lapIndex": 1,
    }
    base.update(overrides)
    return base


def test_parse_splits_basic():
    """基本的なラップデータのパースが正しいこと"""
    raw = _make_raw_splits(
        _make_lap(
            lapIndex=1, distance=1000.0, duration=330.0, averageHR=140.0, maxHR=155.0
        ),
        _make_lap(
            lapIndex=2, distance=1000.0, duration=320.0, averageHR=148.0, maxHR=162.0
        ),
    )
    result = parse_splits(raw)
    assert len(result) == 2
    assert result[0]["split_number"] == 1
    assert result[0]["distance_km"] == 1.0
    assert result[0]["duration_sec"] == 330.0
    assert result[0]["avg_pace"] == "5:30"
    assert result[0]["avg_hr"] == 140
    assert result[0]["max_hr"] == 155

    assert result[1]["split_number"] == 2
    assert result[1]["avg_pace"] == "5:20"


def test_parse_splits_partial_lap():
    """端数ラップ（1km未満）が正しくパースされること"""
    raw = _make_raw_splits(
        _make_lap(lapIndex=1, distance=1000.0, duration=300.0),
        _make_lap(lapIndex=2, distance=500.0, duration=160.0),  # 0.5km
    )
    result = parse_splits(raw)
    assert len(result) == 2
    assert result[1]["distance_km"] == 0.5
    assert result[1]["avg_pace"] == "5:20"  # 160 / 0.5 = 320 sec/km = 5:20


def test_parse_splits_empty():
    """空のレスポンスでも動くこと"""
    assert parse_splits({}) == []
    assert parse_splits({"lapDTOs": []}) == []


def test_parse_splits_missing_hr():
    """心拍データがないラップでNoneになること"""
    raw = _make_raw_splits(
        _make_lap(lapIndex=1, averageHR=None, maxHR=None),
    )
    result = parse_splits(raw)
    assert result[0]["avg_hr"] is None
    assert result[0]["max_hr"] is None
