from __future__ import annotations

from run_coach.config import apply_settings, load_profile, load_settings
from run_coach.graph import compile_graph
from run_coach.state import AgentState


def main() -> None:
    settings = load_settings()
    apply_settings(settings)

    profile = load_profile()
    state = AgentState(user_profile=profile)
    app = compile_graph()
    app.invoke(state)


if __name__ == "__main__":
    main()
