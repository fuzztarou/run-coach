from __future__ import annotations

from run_coach.calendar import WORKOUT_TYPE_LABEL
from run_coach.state import AgentState, Plan

INTENSITY_LABEL = {
    "low": "低",
    "moderate": "中",
    "high": "高",
}

DAY_OF_WEEK = ("月", "火", "水", "木", "金", "土", "日")


def plan_to_markdown(plan: Plan) -> str:
    """Convert a Plan to a Markdown table."""
    lines = [
        f"# トレーニング計画 (Week of {plan.week_start})",
        "",
        "## ワークアウト評価",
        "",
        plan.workout_evaluation,
        "",
        "## 来週のメニュー",
        "",
        "| 日付 | 曜日 | メニュー | 目的 | 時間(min) | 強度 | HR上限 | メモ |",
        "|------|------|----------|------|-----------|------|--------|------|",
    ]

    for workout in plan.workouts:
        intensity = INTENSITY_LABEL.get(
            workout.intensity or "", workout.intensity or "-"
        )
        hr = str(workout.max_hr) if workout.max_hr else "-"
        purpose = workout.purpose or "-"
        duration = workout.duration_min or 0
        notes = workout.notes or ""
        day_name = DAY_OF_WEEK[workout.date.weekday()]
        workout_label = WORKOUT_TYPE_LABEL.get(
            workout.workout_type, workout.workout_type
        )
        lines.append(
            f"| {workout.date} | {day_name} | {workout_label} | {purpose} | {duration} | {intensity} | {hr} | {notes} |"
        )

    lines.extend(
        [
            "",
            f"**負荷サマリー:** {plan.load_summary}",
            "",
            f"**根拠:** {plan.reasoning}",
        ]
    )

    return "\n".join(lines)


def output_plan(state: AgentState) -> AgentState:
    """LangGraphノード: プランをMarkdownで出力する。"""
    if state.plan:
        print()
        print(plan_to_markdown(state.plan))
    return state
