"""SQLite操作モジュール。ワークアウトデータの蓄積・取得を管理する。"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

# DB保存先（Phase 6でCloud Run移行時に変更予定）
DB_PATH = Path("data/run_coach.db")

# 履歴取得のデフォルト期間（日数）
DEFAULT_HISTORY_DAYS = 14

_CREATE_WORKOUTS_TABLE = """\
CREATE TABLE IF NOT EXISTS workouts (
    id                    INTEGER PRIMARY KEY,
    garmin_activity_id    TEXT UNIQUE,          -- Garmin Connect のアクティビティID
    date                  DATE,                 -- ワークアウト実施日
    workout_type          TEXT,                 -- running, trail_running, walking 等
    distance_km           REAL,                 -- 走行距離 (km)
    duration_min          REAL,                 -- 所要時間 (分)
    pace_seconds_per_km   REAL,                 -- 平均ペース (秒/km). 例: 5:30/km = 330.0
    avg_heart_rate_bpm    INTEGER,              -- 平均心拍数 (bpm)
    training_effect       REAL,                 -- Garmin 有酸素トレーニング効果 (0.0-5.0)
    description           TEXT,                 -- Garmin メモ欄の原文
    rpe                   INTEGER,              -- 主観的運動強度 (1-10), 振り返り時に更新
    pain                  TEXT,                 -- 痛みの部位・程度
    comment               TEXT,                 -- 自由コメント
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INSERT_WORKOUT = """\
INSERT OR IGNORE INTO workouts (
    garmin_activity_id, date, workout_type, distance_km,
    duration_min, pace_seconds_per_km, avg_heart_rate_bpm,
    training_effect, description, rpe, pain, comment
) VALUES (
    :garmin_activity_id, :date, :workout_type, :distance_km,
    :duration_min, :pace_seconds_per_km, :avg_heart_rate_bpm,
    :training_effect, :description, :rpe, :pain, :comment
);
"""

_UPDATE_FEEDBACK = """\
UPDATE workouts
SET rpe = :rpe, pain = :pain, comment = :comment
WHERE garmin_activity_id = :garmin_activity_id;
"""


def get_db_path() -> Path:
    """DB保存先パスを返す。"""
    return DB_PATH


def ensure_db() -> None:
    """data/ディレクトリの作成とテーブル初期化をまとめて行う。"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    try:
        init_db(conn)
    finally:
        conn.close()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """SQLite接続を返す。row_factory=sqlite3.Row で辞書ライクにアクセス可能。"""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """テーブルを作成する（存在しなければ）。"""
    conn.execute(_CREATE_WORKOUTS_TABLE)
    conn.commit()


def save_workout(conn: sqlite3.Connection, workout_dict: dict) -> None:
    """ワークアウトを保存する。garmin_activity_idが重複する場合は無視（INSERT OR IGNORE）。"""
    conn.execute(_INSERT_WORKOUT, workout_dict)
    conn.commit()


def update_workout_feedback(
    conn: sqlite3.Connection,
    garmin_activity_id: str,
    feedback_dict: dict,
) -> None:
    """振り返り情報（rpe/pain/comment）を更新する。"""
    params = {
        "garmin_activity_id": garmin_activity_id,
        "rpe": feedback_dict.get("rpe"),
        "pain": feedback_dict.get("pain"),
        "comment": feedback_dict.get("comment"),
    }
    conn.execute(_UPDATE_FEEDBACK, params)
    conn.commit()


def get_unsaved_activity_ids(
    conn: sqlite3.Connection, garmin_activity_ids: list[str]
) -> list[str]:
    """渡されたIDのうち、まだDBに保存されていないものを返す。"""
    if not garmin_activity_ids:
        return []
    placeholders = ",".join("?" for _ in garmin_activity_ids)
    cursor = conn.execute(
        f"SELECT garmin_activity_id FROM workouts WHERE garmin_activity_id IN ({placeholders})",  # noqa: S608
        garmin_activity_ids,
    )
    saved_ids = {row["garmin_activity_id"] for row in cursor}
    return [aid for aid in garmin_activity_ids if aid not in saved_ids]


def get_workout_history(
    conn: sqlite3.Connection, days: int = DEFAULT_HISTORY_DAYS
) -> list[dict]:
    """直近N日間の履歴を取得する。"""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    cursor = conn.execute(
        "SELECT * FROM workouts WHERE date >= ? ORDER BY date DESC",
        (cutoff,),
    )
    return [dict(row) for row in cursor]


def get_workout_by_garmin_id(
    conn: sqlite3.Connection, garmin_activity_id: str
) -> dict | None:
    """garmin_activity_idで1件取得する。"""
    cursor = conn.execute(
        "SELECT * FROM workouts WHERE garmin_activity_id = ?",
        (garmin_activity_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None
