# Phase 5.1: ワークアウト Upsert 対応

## 目的

Garmin上でワークアウトのコメント（description）を後から修正した場合に、DBへ反映されるようにする。

`ON CONFLICT DO NOTHING` → `ON CONFLICT DO UPDATE`（upsert）に変更し、Garmin側の変更をDBに同期する。
また、1件ずつINSERTしていたワークアウト保存をバルクupsertに変更し、DB往復を削減する。

## 変更内容

### 1. `upsert_workouts()` — バルクupsert（`database.py`）

旧 `save_workout()` (1件ずつ) → `upsert_workouts()` (一括) にリネーム・バルク化。

```python
def upsert_workouts(conn, workout_dicts: list[dict]) -> dict[str, int]:
    """ワークアウトをバルクupsertで保存する。
    Returns: {garmin_activity_id: workout_id} のマッピング。
    """
    stmt = insert(workouts).values(workout_dicts)
    stmt = stmt.on_conflict_do_update(
        index_elements=["garmin_activity_id"],
        set_={...},  # 更新対象カラム
    ).returning(workouts.c.id, workouts.c.garmin_activity_id)
```

**更新対象カラム:**

| カラム | 更新する | 理由 |
|--------|----------|------|
| `date` | No | 変わらない |
| `workout_type` | No | 変わらない |
| `distance_km` | Yes | Garmin側で手動補正の可能性 |
| `duration_min` | Yes | 同上 |
| `pace_seconds_per_km` | Yes | distance/durationから再計算 |
| `avg_heart_rate_bpm` | Yes | Garmin側補正の可能性 |
| `training_effect` | Yes | 同上 |
| `description` | Yes | **主目的: コメント修正の反映** |
| `rpe` | Yes | descriptionパース結果 |
| `pain` | Yes | descriptionパース結果 |
| `comment` | Yes | descriptionパース結果 |
| `created_at` | No | 初回登録日時を保持 |

### 2. `save_splits()` → upsert化（`database.py`）

splitsもGarmin側で再計算される可能性があるため、`on_conflict_do_update` に変更。
（元々バルクインサートだったため、バルクupsertへの変更のみ）

### 3. `save_workouts()` ノードの簡素化（`workout_store.py`）

- ループで1件ずつ `upsert_workout()` → `upsert_workouts()` で一括処理
- `get_unsaved_activity_ids()` による事前フィルタを削除（upsertで不要）
- 戻り値の `id_map` を使ってsplits保存をループ

```python
# Before: N回のDB往復
for workout in workouts_with_id:
    workout_id = upsert_workout(conn, workout_dict)
    _save_activity_splits(conn, workout_id, activity_id)

# After: 1回のバルクupsert + N回のsplits取得
workout_dicts = [build_dict(w) for w in workouts_with_id]
id_map = upsert_workouts(conn, workout_dicts)
for activity_id, workout_id in id_map.items():
    _save_activity_splits(conn, workout_id, activity_id)
```

### 4. 削除した関数

| 関数 | 理由 |
|------|------|
| `get_unsaved_activity_ids()` | upsertで不要 |
| `update_workout_feedback()` | upsertでdescriptionごと更新されるため不要 |

## テスト

- バルクupsert（複数件の一括保存）
- 空リストの処理
- 同一 `garmin_activity_id` で2回保存 → 2回目の値で更新
- `created_at`, `date`, `workout_type` が更新されないこと
- splits の upsert: 同じ `(workout_id, split_number)` で更新

## マイグレーション

スキーマ変更なし（ON CONFLICTの動作はアプリ側の変更のみ）。
