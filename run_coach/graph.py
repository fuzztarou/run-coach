from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from run_coach.calendar import fetch_calendar, sync_plan_to_calendar
from run_coach.formatter import output_plan
from run_coach.garmin import fetch_races, fetch_workouts
from run_coach.line import notify_line
from run_coach.plan_review import self_check
from run_coach import planner
from run_coach.state import AgentState
from run_coach.weather import fetch_weather
from run_coach.workout_store import save_workouts


def _should_continue(state: AgentState) -> str:
    """self_check後のルーティング判定。"""
    if state.review_result == "ok":
        return "ok"
    if state.review_retry_count > planner.PLAN_REVIEW_MAX_RETRIES:
        return "ok"
    return "ng"


def build_graph() -> StateGraph:
    """StateGraphを構築して返す。"""
    graph = StateGraph(AgentState)

    graph.add_node("fetch_workouts", fetch_workouts)
    graph.add_node("save_workouts", save_workouts)
    graph.add_node("fetch_races", fetch_races)
    graph.add_node("fetch_calendar", fetch_calendar)
    graph.add_node("fetch_weather", fetch_weather)
    graph.add_node("generate_plan", planner.generate_plan)
    graph.add_node("self_check", self_check)
    graph.add_node("output_plan", output_plan)
    graph.add_node("sync_calendar", sync_plan_to_calendar)
    graph.add_node("notify_line", notify_line)

    graph.add_edge(START, "fetch_workouts")
    graph.add_edge("fetch_workouts", "save_workouts")
    graph.add_edge("save_workouts", "fetch_races")
    graph.add_edge("fetch_races", "fetch_calendar")
    graph.add_edge("fetch_calendar", "fetch_weather")
    graph.add_edge("fetch_weather", "generate_plan")
    graph.add_edge("generate_plan", "self_check")
    graph.add_conditional_edges(
        "self_check",
        _should_continue,
        {"ok": "output_plan", "ng": "generate_plan"},
    )
    graph.add_edge("output_plan", "sync_calendar")
    graph.add_edge("sync_calendar", "notify_line")
    graph.add_edge("notify_line", END)

    return graph


def compile_graph() -> CompiledStateGraph:
    """コンパイル済みグラフを返す。"""
    return build_graph().compile()
