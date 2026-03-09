from __future__ import annotations

from run_coach.config import load_profile
from run_coach.graph import compile_graph
from run_coach.state import AgentState


def main() -> None:
    profile = load_profile()
    state = AgentState(user_profile=profile)
    app = compile_graph()
    app.invoke(state)


if __name__ == "__main__":
    main()
