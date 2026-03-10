from datetime import date, timedelta

import pytest

from run_coach.database import (
    get_connection,
    get_splits_by_workout_id,
    get_unsaved_activity_ids,
    get_workout_by_garmin_id,
    get_workout_history,
    init_db,
    save_splits,
    save_workout,
    update_workout_feedback,
)


@pytest.fixture()
def db(tmp_path):
    """テスト用のインメモリDBを返す。"""
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_db(conn)
    yield conn
    conn.close()


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


def test_save_and_get_workout(db):
    """保存・取得ができること。"""
    save_workout(db, _make_workout())
    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["distance_km"] == 10.0
    assert result["pace_seconds_per_km"] == 330.0
    assert result["avg_heart_rate_bpm"] == 150
    assert result["date"] == date(2026, 3, 1)


def test_no_duplicate_workout(db):
    """garmin_activity_id重複時にエラーにならないこと。"""
    save_workout(db, _make_workout())
    save_workout(db, _make_workout())  # 2回目
    cursor = db.execute("SELECT count(*) as cnt FROM workouts")
    assert cursor.fetchone()["cnt"] == 1


def test_save_workout_with_feedback(db):
    """振り返り付きで保存できること。"""
    save_workout(db, _make_workout(rpe=7, pain="右ひざ", comment="調子良かった"))
    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["rpe"] == 7
    assert result["pain"] == "右ひざ"
    assert result["comment"] == "調子良かった"


def test_update_workout_feedback(db):
    """rpe/pain/commentが更新されること。"""
    save_workout(db, _make_workout())
    update_workout_feedback(
        db, "123", {"rpe": 7, "pain": None, "comment": "調子良かった"}
    )
    result = get_workout_by_garmin_id(db, "123")
    assert result is not None
    assert result["rpe"] == 7
    assert result["pain"] is None
    assert result["comment"] == "調子良かった"


def test_get_unsaved_activity_ids(db):
    """未保存分のIDが正しく検出されること。"""
    save_workout(db, _make_workout(garmin_activity_id="100"))
    save_workout(db, _make_workout(garmin_activity_id="200"))

    unsaved = get_unsaved_activity_ids(db, ["100", "200", "300", "400"])
    assert sorted(unsaved) == ["300", "400"]


def test_get_unsaved_activity_ids_empty(db):
    """空リストを渡しても動くこと。"""
    assert get_unsaved_activity_ids(db, []) == []


def test_get_workout_history(db):
    """期間指定で取得できること。"""
    today = date.today()
    save_workout(db, _make_workout(garmin_activity_id="recent", date=today.isoformat()))
    old_date = today - timedelta(days=100)
    save_workout(db, _make_workout(garmin_activity_id="old", date=old_date.isoformat()))

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
    save_workout(db, _make_workout())
    workout = get_workout_by_garmin_id(db, "123")
    assert workout is not None

    splits = _make_splits(2)
    save_splits(db, workout["id"], splits)

    result = get_splits_by_workout_id(db, workout["id"])
    assert len(result) == 2
    assert result[0]["split_number"] == 1
    assert result[0]["avg_pace"] == "5:30"
    assert result[0]["avg_hr"] == 140
    assert result[1]["split_number"] == 2
    assert result[1]["avg_pace"] == "5:25"


def test_splits_no_duplicate(db):
    """同一workout_idのsplitsを重複保存しないこと。"""
    save_workout(db, _make_workout())
    workout = get_workout_by_garmin_id(db, "123")
    assert workout is not None

    splits = _make_splits(2)
    save_splits(db, workout["id"], splits)
    save_splits(db, workout["id"], splits)  # 2回目はスキップされる

    result = get_splits_by_workout_id(db, workout["id"])
    assert len(result) == 2


def test_splits_linked_to_workout(db):
    """workout_idで正しく紐付けされること。"""
    save_workout(db, _make_workout(garmin_activity_id="A1"))
    save_workout(db, _make_workout(garmin_activity_id="A2"))

    w1 = get_workout_by_garmin_id(db, "A1")
    w2 = get_workout_by_garmin_id(db, "A2")
    assert w1 is not None and w2 is not None

    save_splits(db, w1["id"], _make_splits(3))
    save_splits(db, w2["id"], _make_splits(1))

    assert len(get_splits_by_workout_id(db, w1["id"])) == 3
    assert len(get_splits_by_workout_id(db, w2["id"])) == 1


def test_get_splits_empty(db):
    """splitsがないworkoutは空リストを返すこと。"""
    save_workout(db, _make_workout())
    workout = get_workout_by_garmin_id(db, "123")
    assert workout is not None
    assert get_splits_by_workout_id(db, workout["id"]) == []
