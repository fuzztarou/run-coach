from __future__ import annotations

from run_coach.config import load_profile
from run_coach.formatter import plan_to_markdown
from run_coach.garmin import fetch_garmin
from run_coach.planner import generate_plan
from run_coach.state import AgentState


def main() -> None:
    profile = load_profile()
    state = AgentState(user_profile=profile)

    print("Garmin Connect からデータを取得中...")
    state = fetch_garmin(state)
    print(f"  {len(state.signals.recent_workouts)} 件のワークアウトを取得しました")

    print("トレーニング計画を生成中...")
    state = generate_plan(state)

    if state.plan:
        print()
        print(plan_to_markdown(state.plan))


if __name__ == "__main__":
    main()
