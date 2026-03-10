"""SQLAlchemy テーブル定義。"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

workouts = Table(
    "workouts",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("garmin_activity_id", Text, unique=True, nullable=False),
    Column("date", Date, nullable=False),
    Column("workout_type", Text, nullable=False),
    Column("distance_km", Float),
    Column("duration_min", Float),
    Column("pace_seconds_per_km", Float),
    Column("avg_heart_rate_bpm", Integer),
    Column("training_effect", Float),
    Column("description", Text),
    Column("rpe", Integer),
    Column("pain", Text),
    Column("comment", Text),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

workout_splits = Table(
    "workout_splits",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "workout_id",
        BigInteger,
        ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("split_number", Integer, nullable=False),
    Column("distance_km", Float),
    Column("duration_sec", Float),
    Column("avg_pace", Text),
    Column("avg_hr", Integer),
    Column("max_hr", Integer),
    Column("elevation_gain", Float),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("workout_id", "split_number"),
)
