# Phase 5: PostgreSQL移行

SQLite前提のローカル実装を、Cloud Run / Supabaseで運用できるPostgreSQL構成に移行する。

## ゴール

- ローカル開発環境でもPostgreSQLを使う
- 本番（Cloud Run）でも同じDB前提で動く
- `workouts` / `workout_splits` の永続化をSupabaseへ移せる状態にする
- 以降のCloud Runデプロイで、DB差異を原因とする不具合を避ける

## 方針

- RAG導入は後回しにする
- 個人メモ活用もこのフェーズでは行わない
- DBまわりの一貫性を優先し、ローカルも本番もPostgreSQL前提に揃える
- 接続設定は `DATABASE_URL` に統一する
- DBアクセスは `SQLAlchemy Core`、migrationは `Alembic` を採用する

## フロー

```mermaid
flowchart LR
    DEV[ローカル開発] --> LPG[(PostgreSQL)]
    CR[Cloud Run] --> SB[(Supabase PostgreSQL)]

    LPG -.同一スキーマ / 同一SQL方針.- SB

    APP[run-coach] --> DBLAYER[DBアクセス層]
    DBLAYER --> LPG
    DBLAYER --> SB

    style LPG fill:#336791,color:#fff
    style SB fill:#3ecf8e,color:#fff
    style DBLAYER fill:#ff9f43,color:#fff
```

## やること

- [ ] ローカルPostgreSQL起動方法を用意（例: Docker Compose）
- [ ] DB接続設定を `DATABASE_URL` ベースに統一
- [ ] SQLite依存の実装をPostgreSQL対応へ変更
- [ ] `workouts` / `workout_splits` スキーマをPostgreSQL向けに定義
- [ ] migration手順を用意
- [ ] テストをPostgreSQL前提で通す

## 変更対象

### 接続方式

- ローカル: Docker上のPostgreSQL
- 本番: Supabase PostgreSQL
- アプリ: `DATABASE_URL` を参照して接続

例:

```bash
# ローカル
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/run_coach

# Cloud Run / Supabase
DATABASE_URL=postgresql://postgres.xxxxx:[PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
```

### DB実装

現在の `sqlite3` 直書き実装を見直し、少なくとも以下を吸収する:

- `sqlite3` から `SQLAlchemy Core` へ移行
- `INSERT OR IGNORE` → PostgreSQLの `ON CONFLICT DO NOTHING`
- SQLite固有の `row_factory` 依存の見直し
- `DATE` / `TIMESTAMP` / 自動採番の差異吸収
- `workout_splits` は `UNIQUE (workout_id, split_number)` を前提に `ON CONFLICT DO NOTHING` で重複回避する

## ライブラリ方針

- DB接続/クエリ: `SQLAlchemy Core`
- PostgreSQLドライバ: `psycopg`
- migration: `Alembic`

理由:

- PostgreSQL方言を吸収しやすい
- 生SQLより差分管理しやすい
- migrationをローカル/本番で共通化できる

## ローカル開発環境

ローカルではDocker ComposeでPostgreSQLを起動する。

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: run_coach
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

```bash
docker compose up -d
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/run_coach
alembic upgrade head
```

## スキーマ方針

テーブル構造自体は維持しつつ、PostgreSQL前提にする。

```sql
CREATE TABLE workouts (
    id                  BIGSERIAL PRIMARY KEY,
    garmin_activity_id  TEXT UNIQUE NOT NULL,
    date                DATE NOT NULL,
    workout_type        TEXT NOT NULL,
    distance_km         DOUBLE PRECISION,
    duration_min        DOUBLE PRECISION,
    pace_seconds_per_km DOUBLE PRECISION,
    avg_heart_rate_bpm  INTEGER,
    training_effect     DOUBLE PRECISION,
    description         TEXT,
    rpe                 INTEGER,
    pain                TEXT,
    comment             TEXT,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workout_splits (
    id              BIGSERIAL PRIMARY KEY,
    workout_id      BIGINT NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    split_number    INTEGER NOT NULL,
    distance_km     DOUBLE PRECISION,
    duration_sec    DOUBLE PRECISION,
    avg_pace        TEXT,
    avg_hr          INTEGER,
    max_hr          INTEGER,
    elevation_gain  DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workout_id, split_number)
);
```

## migration方針

- `Alembic` を採用する
- 初期段階では `workouts` / `workout_splits` の作成migrationを用意する
- アプリ起動時の自動 `CREATE TABLE IF NOT EXISTS` 依存は減らす
- ローカルでも本番でも同じmigrationを使う

## 既存データの扱い

- 既存SQLiteデータが少量なら、開発中は破棄して再取得でもよい
- 残したい場合は、SQLite → PostgreSQL の一回限りの移行スクリプトを用意する
- 本番運用前にSQLite依存を残さない

## テスト方針

- [ ] PostgreSQLで `workouts` CRUD が通ること
- [ ] PostgreSQLで `workout_splits` CRUD が通ること
- [ ] 重複排除（`garmin_activity_id UNIQUE`）が期待通りに動くこと
- [ ] `workout_splits(workout_id, split_number)` の重複防止が動くこと
- [ ] `save_workouts()` が既存フローのまま動くこと
- [ ] CIでもPostgreSQLサービスを立ててテストできること

```python
def test_save_and_get_workout(db):
    save_workout(db, {...})
    result = get_workout_by_garmin_id(db, "123")
    assert result["garmin_activity_id"] == "123"

def test_no_duplicate_workout(db):
    save_workout(db, {...})
    save_workout(db, {...})
    assert count_workouts(db) == 1
```

## 完了条件

- ローカルでPostgreSQLを使って `pytest` が通る
- `DATABASE_URL` だけで接続先を切り替えられる
- Supabaseに接続してアプリが動く
