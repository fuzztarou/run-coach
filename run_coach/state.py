from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, computed_field


class RunsPerWeek(BaseModel):
    min: int = Field(ge=1, le=7)
    max: int = Field(ge=1, le=7)


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class UserProfile(BaseModel):
    birthday: date
    goal: str
    runs_per_week: RunsPerWeek
    injury_history: list[str] = Field(default_factory=list)
    location: Location | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age(self) -> int:
        today = date.today()
        return (
            today.year
            - self.birthday.year
            - ((today.month, today.day) < (self.birthday.month, self.birthday.day))
        )


class WorkoutSummary(BaseModel):
    date: date
    type: str
    distance_km: float
    duration_min: float
    avg_pace: str  # e.g. "5:30"
    avg_hr: int | None = None
    training_effect: float | None = None


class Signals(BaseModel):
    recent_workouts: list[WorkoutSummary] = Field(default_factory=list)
    hrv_trend: str | None = None
    training_load: str | None = None
    race_predictions: dict[str, str] | None = None


class WorkoutPlan(BaseModel):
    date: date
    workout_type: str
    purpose: str | None = ""
    duration_min: int | None = 0
    intensity: str | None = "low"
    max_hr: int | None = None
    notes: str | None = ""


class Plan(BaseModel):
    week_start: date
    workout_evaluation: str
    workouts: list[WorkoutPlan]
    load_summary: str
    reasoning: str


class CalendarSlot(BaseModel):
    date: date
    available: bool
    events: list[str] = Field(default_factory=list)


class DailyWeather(BaseModel):
    date: date
    temperature_max: float
    temperature_min: float
    precipitation_probability: int = Field(ge=0, le=100)
    precipitation_sum: float
    wind_speed_max: float


class RaceEvent(BaseModel):
    event_name: str
    date: date
    distance_km: float | None = None
    goal_time_seconds: float | None = None
    location: str | None = None
    is_primary: bool = False


class Constraints(BaseModel):
    available_slots: list[CalendarSlot] = Field(default_factory=list)
    weather: list[DailyWeather] = Field(default_factory=list)
    races: list[RaceEvent] = Field(default_factory=list)


class AgentState(BaseModel):
    user_profile: UserProfile
    signals: Signals = Field(default_factory=Signals)
    constraints: Constraints = Field(default_factory=Constraints)
    plan: Plan | None = None
    review_result: str | None = None  # "ok" | "ng"
    review_violations: list[str] = Field(default_factory=list)
    review_retry_count: int = 0
