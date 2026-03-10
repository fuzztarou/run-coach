# Phase 4.5: workout_splits（ラップデータ蓄積）

## ゴール

1km毎のラップデータをSQLiteに蓄積し、ペース分析やLLMへの入力データとして活用できるようにする。

## やること

- [ ] workout_splitsテーブル作成
- [ ] Garmin APIからsplits取得（`client.get_activity_splits(activity_id)`）
- [ ] 取得したsplitsデータをworkout_splitsテーブルに保存
- [ ] ワークアウト保存時にsplitsも一緒に取得・保存する処理の統合

## SQLiteテーブル設計

```sql
CREATE TABLE workout_splits (
    id INTEGER PRIMARY KEY,
    workout_id INTEGER REFERENCES workouts(id),
    split_number INTEGER,
    distance_km REAL,
    duration_sec REAL,
    avg_pace TEXT,
    avg_hr INTEGER,
    max_hr INTEGER,
    elevation_gain REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

> **Note**: `workout_id` は workouts テーブルの `id` を参照する。Phase 4 で workouts テーブルが作成済みであることが前提。

## テスト方針

- [ ] workout_splits CRUD: ラップデータの保存・取得
- [ ] workoutとの紐付け: workout_idで正しくリレーションされるか
- [ ] 重複排除: 同一ワークアウトのsplitsを重複保存しないか

```python
# テスト例
def test_save_and_get_splits(db):
    # workoutを先に保存
    save_workout(db, {"garmin_activity_id": "123", "date": "2026-03-01", "distance_km": 10.0, ...})
    workout = get_workout_by_garmin_id(db, "123")

    splits = [
        {"split_number": 1, "distance_km": 1.0, "duration_sec": 330, "avg_pace": "5:30", "avg_hr": 140, "max_hr": 150, "elevation_gain": 5.0},
        {"split_number": 2, "distance_km": 1.0, "duration_sec": 325, "avg_pace": "5:25", "avg_hr": 145, "max_hr": 155, "elevation_gain": 3.0},
    ]
    save_splits(db, workout["id"], splits)
    result = get_splits_by_workout_id(db, workout["id"])
    assert len(result) == 2
    assert result[0]["avg_pace"] == "5:30"
```
