"""PostgreSQL操作モジュール。ワークアウトデータの蓄積・取得を管理する。"""

from __future__ import annotations

import os
from datetime import date, timedelta

from sqlalchemy import Connection, Engine, create_engine, select, text, update
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


def save_workout(conn: Connection, workout_dict: dict) -> int | None:
    """ワークアウトを保存する。garmin_activity_idが重複する場合は無視。

    Returns:
        挿入された行のID。重複スキップ時はNone。
    """
    stmt = (
        insert(workouts)
        .values(**workout_dict)
        .on_conflict_do_nothing(index_elements=["garmin_activity_id"])
        .returning(workouts.c.id)
    )
    result = conn.execute(stmt)
    row = result.fetchone()
    return row[0] if row else None


def update_workout_feedback(
    conn: Connection,
    garmin_activity_id: str,
    feedback_dict: dict,
) -> None:
    """振り返り情報（rpe/pain/comment）を更新する。"""
    stmt = (
        update(workouts)
        .where(workouts.c.garmin_activity_id == garmin_activity_id)
        .values(
            rpe=feedback_dict.get("rpe"),
            pain=feedback_dict.get("pain"),
            comment=feedback_dict.get("comment"),
        )
    )
    conn.execute(stmt)


def get_unsaved_activity_ids(
    conn: Connection, garmin_activity_ids: list[str]
) -> list[str]:
    """渡されたIDのうち、まだDBに保存されていないものを返す。"""
    if not garmin_activity_ids:
        return []
    stmt = select(workouts.c.garmin_activity_id).where(
        workouts.c.garmin_activity_id.in_(garmin_activity_ids)
    )
    result = conn.execute(stmt)
    saved_ids = {row[0] for row in result}
    return [aid for aid in garmin_activity_ids if aid not in saved_ids]


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
    """ラップデータをバルクインサートで一括保存する。重複はスキップ。"""
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
    stmt = (
        insert(workout_splits)
        .values(rows)
        .on_conflict_do_nothing(constraint="workout_splits_workout_id_split_number_key")
    )
    conn.execute(stmt)


def get_splits_by_workout_id(conn: Connection, workout_id: int) -> list[dict]:
    """workout_idに紐づくラップデータを取得する。"""
    stmt = (
        select(workout_splits)
        .where(workout_splits.c.workout_id == workout_id)
        .order_by(workout_splits.c.split_number)
    )
    result = conn.execute(stmt)
    return [row._asdict() for row in result]
