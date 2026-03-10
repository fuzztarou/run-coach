# Phase 4.5: workout_splits（ラップデータ蓄積）実装計画

## Context

Phase 4（SQLite + Garmin振り返り）が完了し、workoutsテーブルにワークアウトのサマリーデータを蓄積できるようになった。
Phase 4.5では `client.get_activity_splits(activity_id)` でラップデータを取得し、
`workout_splits`テーブルに蓄積する。

## Garmin API調査結果

`GET /activity-service/activity/{id}/splits` のレスポンス:

```json
{
  "activityId": 22111745238,
  "lapDTOs": [
    {
      "distance": 1000.0,       // メートル
      "duration": 588.802,      // 秒
      "elevationGain": 6.0,     // メートル
      "averageHR": 105.0,       // bpm
      "maxHR": 119.0,           // bpm
      "lapIndex": 1,            // 1始まり
      "averageSpeed": 1.698,    // m/s
      "intensityType": "ACTIVE"
    }
  ]
}
```

## 実装手順

### Step 1: database.py — workout_splitsテーブル + CRUD

- `_CREATE_SPLITS_TABLE`: テーブル定義
- `init_db()`: 既存のworkoutsテーブル作成に加えてsplitsテーブルも作成
- `save_splits(conn, workout_id, splits_list)`: ラップ一括保存
- `get_splits_by_workout_id(conn, workout_id)`: ラップ取得

### Step 2: garmin.py — splits取得・パース

- `fetch_activity_splits(client, activity_id)`: APIからsplits取得 → dict list変換
- ペース計算: `duration / (distance / 1000)` → "M:SS"形式

### Step 3: workout_store.py — splits保存統合

- `save_workouts()` ノード内で、新規保存したワークアウトのsplitsも取得・保存
- Garmin APIコール追加（`_login()` でクライアント取得）

### Step 4: テスト

- `test_database.py`: splits CRUD、workoutとの紐付け、重複排除
- `test_garmin.py`: parse_splits のユニットテスト

## 変更対象ファイル

| ファイル | 変更種別 |
|----------|----------|
| `run_coach/database.py` | 変更 |
| `run_coach/garmin.py` | 変更 |
| `run_coach/workout_store.py` | 変更 |
| `tests/test_database.py` | 変更 |
| `tests/test_garmin.py` | 変更 |
