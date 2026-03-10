"""テスト共有fixture。"""

import pytest
from sqlalchemy import text

from run_coach.database import create_tables, get_engine


@pytest.fixture(scope="session")
def _setup_tables():
    """テスト用DBにテーブルを作成（session scope）。"""
    engine = get_engine()
    create_tables(engine)


@pytest.fixture()
def db(_setup_tables):
    """各テストにトランザクション内の接続を提供し、終了時にrollback。"""
    engine = get_engine()
    with engine.connect() as conn:
        trans = conn.begin()
        yield conn
        trans.rollback()


@pytest.fixture()
def clean_db(_setup_tables):
    """save_workouts()ノードテスト用fixture。

    ノードが自前でcommitするため通常のrollback fixtureでは隔離できない。
    setup/teardownでTRUNCATEを実行する。
    """
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE workout_splits, workouts CASCADE"))
        conn.commit()
    yield
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE workout_splits, workouts CASCADE"))
        conn.commit()
