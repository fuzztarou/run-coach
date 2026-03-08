from __future__ import annotations

from run_coach.calendar import fetch_calendar
from run_coach.config import load_profile
from run_coach.formatter import plan_to_markdown
from run_coach.garmin import fetch_workouts, fetch_races
from run_coach.planner import generate_plan_with_review
from run_coach.state import AgentState
from run_coach.weather import fetch_weather


def main() -> None:
    profile = load_profile()
    state = AgentState(user_profile=profile)

    print("Garmin Connect からデータを取得中...")
    state = fetch_workouts(state)
    print(f"  {len(state.signals.recent_workouts)} 件のワークアウトを取得しました")

    print("大会情報を取得中...")
    state = fetch_races(state)
    print(f"  {len(state.constraints.races)} 件の大会を取得しました")

    print("カレンダーを取得中...")
    state = fetch_calendar(state)
    print(f"  {len(state.constraints.available_slots)} 日分のスロットを取得しました")

    print("天気予報を取得中...")
    state = fetch_weather(state)
    print(f"  {len(state.constraints.weather)} 日分の天気予報を取得しました")

    print("トレーニング計画を生成中...")
    state = generate_plan_with_review(state)

    if state.review_violations:
        print(
            f"  プランレビュー: {len(state.review_violations)} 件の指摘を修正しました"
        )
    else:
        print("  プランレビュー: OK")

    if state.plan:
        print()
        print(plan_to_markdown(state.plan))


if __name__ == "__main__":
    main()
