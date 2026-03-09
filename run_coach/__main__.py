from __future__ import annotations

from run_coach.config import load_profile, load_settings
from run_coach.graph import compile_graph
from run_coach.planner import set_plan_review_max_retries
from run_coach.prompt import set_llm_model
from run_coach.state import AgentState


def main() -> None:
    settings = load_settings()
    set_llm_model(settings["llm_model"])
    set_plan_review_max_retries(int(settings["plan_review_max_retries"]))

    profile = load_profile()
    state = AgentState(user_profile=profile)
    app = compile_graph()
    app.invoke(state)


if __name__ == "__main__":
    main()
