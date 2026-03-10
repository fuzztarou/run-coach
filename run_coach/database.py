"""PostgreSQL操作モジュール。ワークアウトデータの蓄積・取得を管理する。"""

from __future__ import annotations

import os
from datetime import date, timedelta

from sqlalchemy import Connection, Engine, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert

from run_coach.models import metadata, workout_splits, workouts

# 履歴取得のデフォルト期間（日数）
DEFAULT_HISTORY_DAYS = 14

# 必須テーブル一覧（check_connection で存在確認）
_REQUIRED_TABLES = {"workouts", "workout_splits"}

_engine: Engine | None = None


def get_database_url() -> str:
    """DATABASE_URL環境変数を優先し、未設定ならsettings.yamlのdb_portからURLを組み立てる。"""
    database_url = os.environ.get("DATABASE_URL")
    if database_url is not None:
        return database_url

    from run_coach.config import load_settings

    settings = load_settings()
    port = int(settings["db_port"])
    return f"postgresql+psycopg://postgres:postgres@localhost:{port}/run_coach"


def get_engine(url: str | None = None) -> Engine:
    """SQLAlchemy Engineを返す。

    - url指定時: キャッシュせず都度生成（テスト用）
    - url未指定時: DATABASE_URL or settings.yamlからEngine生成（モジュールキャッシュ）
    """
    global _engine
    if url is not None:
        return create_engine(url, connect_args={"prepare_threshold": 0})
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            connect_args={"prepare_threshold": 0},
        )
    return _engine


def reset_engine() -> None:
    """キャッシュされたEngineを破棄する（テスト用）。"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def check_connection() -> None:
    """PostgreSQL接続確認 + 必須テーブル存在チェック。"""
    from sqlalchemy.exc import OperationalError

    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

            result = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' "
                    "AND tablename = ANY(:tables)"
                ),
                {"tables": list(_REQUIRED_TABLES)},
            )
            existing = {row[0] for row in result}
            missing = _REQUIRED_TABLES - existing
            if missing:
                raise RuntimeError(
                    f"テーブル {missing} が見つかりません。"
                    "`alembic upgrade head` を実行してください。"
                )
    except OperationalError as exc:
        raise RuntimeError(
            "PostgreSQLに接続できません。`docker compose up -d` でDBを起動し、"
            "DATABASE_URL環境変数またはconfig/settings.yamlのdb_portを確認してください。"
        ) from exc


def create_tables(engine: Engine) -> None:
    """テスト専用: metadata.create_all でテーブルを作成する。"""
    metadata.create_all(engine)


def upsert_workouts(conn: Connection, workout_dicts: list[dict]) -> dict[str, int]:
    """ワークアウトをバルクupsertで保存する。

    garmin_activity_idが既存の場合はGarmin側の変更を反映（description修正等）。
    date, workout_type, created_at は初回登録値を保持する。

    Returns:
        {garmin_activity_id: workout_id} のマッピング。
    """
    if not workout_dicts:
        return {}
    insert_stmt = insert(workouts).values(workout_dicts)
    conflict_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["garmin_activity_id"],
        set_={
            "distance_km": insert_stmt.excluded.distance_km,
            "duration_min": insert_stmt.excluded.duration_min,
            "pace_seconds_per_km": insert_stmt.excluded.pace_seconds_per_km,
            "avg_heart_rate_bpm": insert_stmt.excluded.avg_heart_rate_bpm,
            "training_effect": insert_stmt.excluded.training_effect,
            "description": insert_stmt.excluded.description,
            "rpe": insert_stmt.excluded.rpe,
            "pain": insert_stmt.excluded.pain,
            "comment": insert_stmt.excluded.comment,
        },
    )
    returning_stmt = conflict_stmt.returning(
        workouts.c.id, workouts.c.garmin_activity_id
    )
    rows = conn.execute(returning_stmt).fetchall()
    return {row.garmin_activity_id: row.id for row in rows}


def get_workout_history(
    conn: Connection, days: int = DEFAULT_HISTORY_DAYS
) -> list[dict]:
    """直近N日間の履歴を取得する。"""
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(workouts)
        .where(workouts.c.date >= cutoff)
        .order_by(workouts.c.date.desc())
    )
    result = conn.execute(stmt)
    return [row._asdict() for row in result]


def get_workout_by_garmin_id(conn: Connection, garmin_activity_id: str) -> dict | None:
    """garmin_activity_idで1件取得する。"""
    stmt = select(workouts).where(workouts.c.garmin_activity_id == garmin_activity_id)
    row = conn.execute(stmt).fetchone()
    return row._asdict() if row else None


def save_splits(conn: Connection, workout_id: int, splits: list[dict]) -> None:
    """ラップデータをupsertで一括保存する。既存データは最新値で更新。"""
    if not splits:
        return
    rows = [
        {
            "workout_id": workout_id,
            "split_number": s["split_number"],
            "distance_km": s["distance_km"],
            "duration_sec": s["duration_sec"],
            "avg_pace": s["avg_pace"],
            "avg_hr": s.get("avg_hr"),
            "max_hr": s.get("max_hr"),
            "elevation_gain": s.get("elevation_gain"),
        }
        for s in splits
    ]
    insert_stmt = insert(workout_splits).values(rows)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="workout_splits_workout_id_split_number_key",
        set_={
            "distance_km": insert_stmt.excluded.distance_km,
            "duration_sec": insert_stmt.excluded.duration_sec,
            "avg_pace": insert_stmt.excluded.avg_pace,
            "avg_hr": insert_stmt.excluded.avg_hr,
            "max_hr": insert_stmt.excluded.max_hr,
            "elevation_gain": insert_stmt.excluded.elevation_gain,
        },
    )
    conn.execute(upsert_stmt)


def get_splits_by_workout_id(conn: Connection, workout_id: int) -> list[dict]:
    """workout_idに紐づくラップデータを取得する。"""
    stmt = (
        select(workout_splits)
        .where(workout_splits.c.workout_id == workout_id)
        .order_by(workout_splits.c.split_number)
    )
    result = conn.execute(stmt)
    return [row._asdict() for row in result]
