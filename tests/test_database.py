from datetime import date, timedelta

from run_coach.database import (
    get_splits_by_workout_id,
    get_workout_by_garmin_id,
    get_workout_history,
    save_splits,
    upsert_workouts,
)


def _make_workout(**overrides) -> dict:
    base = {
        "garmin_activity_id": "123",
        "date": "2026-03-01",
        "workout_type": "running",
        "distance_km": 10.0,
        "duration_min": 55.0,
        "pace_seconds_per_km": 330.0,
        "avg_heart_rate_bpm": 150,
        "training_effect": 3.2,
        "description": "",
        "rpe": None,
        "pain": None,
        "comment": None,
    }
    base.update(overrides)
    return base


def _upsert_one(db, **overrides) -> int:
    """テスト用ヘルパー: 1件upsertしてworkout_idを返す。"""
    workout = _make_workout(**overrides)
    id_map = upsert_workouts(db, [workout])
    return id_map[workout["garmin_activity_id"]]


def test_save_and_get_workout(db):
    """保存・取得ができること。"""
    _upsert_one(db)
    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["distance_km"] == 10.0
    assert result["pace_seconds_per_km"] == 330.0
    assert result["avg_heart_rate_bpm"] == 150
    assert result["date"] == date(2026, 3, 1)


def test_upsert_workouts_bulk(db):
    """複数件を一括upsertできること。"""
    workout_dicts = [
        _make_workout(garmin_activity_id="A1", distance_km=5.0),
        _make_workout(garmin_activity_id="A2", distance_km=10.0),
        _make_workout(garmin_activity_id="A3", distance_km=15.0),
    ]
    id_map = upsert_workouts(db, workout_dicts)
    assert set(id_map.keys()) == {"A1", "A2", "A3"}

    w1 = get_workout_by_garmin_id(db, "A1")
    w3 = get_workout_by_garmin_id(db, "A3")
    assert w1 is not None and w1["distance_km"] == 5.0
    assert w3 is not None and w3["distance_km"] == 15.0


def test_upsert_workouts_empty(db):
    """空リストを渡しても動くこと。"""
    id_map = upsert_workouts(db, [])
    assert id_map == {}


def test_upsert_workout_updates_fields(db):
    """同一garmin_activity_idで2回保存すると、2回目の値で更新されること。"""
    _upsert_one(db, description="初回コメント", comment="初回")
    _upsert_one(db, description="修正コメント", comment="修正後")

    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["description"] == "修正コメント"
    assert result["comment"] == "修正後"


def test_upsert_workout_no_duplicate(db):
    """upsert後もレコード数は1件であること。"""
    _upsert_one(db)
    _upsert_one(db, distance_km=12.0)

    from sqlalchemy import text

    row = db.execute(
        text("SELECT count(*) FROM workouts WHERE garmin_activity_id = '123'")
    ).fetchone()
    assert row[0] == 1

    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["distance_km"] == 12.0


def test_upsert_workout_preserves_created_at(db):
    """upsertでcreated_atが変わらないこと。"""
    _upsert_one(db)
    original = get_workout_by_garmin_id(db, "123")
    assert original is not None

    _upsert_one(db, description="更新")
    updated = get_workout_by_garmin_id(db, "123")
    assert updated is not None

    assert original["created_at"] == updated["created_at"]


def test_upsert_workout_preserves_date_and_type(db):
    """upsertでdate, workout_typeは初回値が保持されること。"""
    _upsert_one(db, date="2026-03-01", workout_type="running")
    _upsert_one(db, date="2026-03-02", workout_type="trail_running")

    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["date"] == date(2026, 3, 1)
    assert result["workout_type"] == "running"


def test_upsert_workout_with_feedback(db):
    """振り返り付きで保存できること。"""
    _upsert_one(db, rpe=7, pain="右ひざ", comment="調子良かった")
    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["rpe"] == 7
    assert result["pain"] == "右ひざ"
    assert result["comment"] == "調子良かった"


def test_get_workout_history(db):
    """期間指定で取得できること。"""
    today = date.today()
    _upsert_one(db, garmin_activity_id="recent", date=today.isoformat())
    old_date = today - timedelta(days=100)
    _upsert_one(db, garmin_activity_id="old", date=old_date.isoformat())

    history = get_workout_history(db, days=90)
    ids = [w["garmin_activity_id"] for w in history]
    assert "recent" in ids
    assert "old" not in ids


def test_get_workout_by_garmin_id_not_found(db):
    """存在しないIDはNoneを返すこと。"""
    assert get_workout_by_garmin_id(db, "nonexistent") is None


# --- workout_splits テスト ---


def _make_splits(count: int = 3) -> list[dict]:
    """テスト用のラップデータリストを生成する。"""
    return [
        {
            "split_number": i + 1,
            "distance_km": 1.0,
            "duration_sec": 330.0 - i * 5,
            "avg_pace": f"5:{30 - i * 5:02d}",
            "avg_hr": 140 + i * 5,
            "max_hr": 150 + i * 5,
            "elevation_gain": 3.0 + i,
        }
        for i in range(count)
    ]


def test_save_and_get_splits(db):
    """ラップデータの保存・取得ができること。"""
    workout_id = _upsert_one(db)

    splits = _make_splits(2)
    save_splits(db, workout_id, splits)

    result = get_splits_by_workout_id(db, workout_id)
    assert len(result) == 2
    assert result[0]["split_number"] == 1
    assert result[0]["avg_pace"] == "5:30"
    assert result[0]["avg_hr"] == 140
    assert result[1]["split_number"] == 2
    assert result[1]["avg_pace"] == "5:25"


def test_upsert_splits(db):
    """同一(workout_id, split_number)で2回保存すると更新されること。"""
    workout_id = _upsert_one(db)

    splits_v1 = [
        {
            "split_number": 1,
            "distance_km": 1.0,
            "duration_sec": 300.0,
            "avg_pace": "5:00",
            "avg_hr": 140,
            "max_hr": 150,
            "elevation_gain": 3.0,
        },
    ]
    save_splits(db, workout_id, splits_v1)

    splits_v2 = [
        {
            "split_number": 1,
            "distance_km": 1.0,
            "duration_sec": 290.0,
            "avg_pace": "4:50",
            "avg_hr": 145,
            "max_hr": 155,
            "elevation_gain": 4.0,
        },
    ]
    save_splits(db, workout_id, splits_v2)

    result = get_splits_by_workout_id(db, workout_id)
    assert len(result) == 1
    assert result[0]["duration_sec"] == 290.0
    assert result[0]["avg_pace"] == "4:50"
    assert result[0]["avg_hr"] == 145


def test_splits_no_duplicate(db):
    """同一workout_idのsplitsを重複保存してもレコード数が増えないこと。"""
    workout_id = _upsert_one(db)

    splits = _make_splits(2)
    save_splits(db, workout_id, splits)
    save_splits(db, workout_id, splits)  # 2回目はupsert

    result = get_splits_by_workout_id(db, workout_id)
    assert len(result) == 2


def test_splits_linked_to_workout(db):
    """workout_idで正しく紐付けされること。"""
    id_map = upsert_workouts(
        db,
        [
            _make_workout(garmin_activity_id="A1"),
            _make_workout(garmin_activity_id="A2"),
        ],
    )

    save_splits(db, id_map["A1"], _make_splits(3))
    save_splits(db, id_map["A2"], _make_splits(1))

    assert len(get_splits_by_workout_id(db, id_map["A1"])) == 3
    assert len(get_splits_by_workout_id(db, id_map["A2"])) == 1


def test_get_splits_empty(db):
    """splitsがないworkoutは空リストを返すこと。"""
    workout_id = _upsert_one(db)
    assert get_splits_by_workout_id(db, workout_id) == []
