import json
from datetime import date

from run_coach import planner
from run_coach.graph import _should_continue, compile_graph
from run_coach.state import (
    AgentState,
    Plan,
    RunsPerWeek,
    UserProfile,
    WorkoutPlan,
)


def _make_state() -> AgentState:
    return AgentState(
        user_profile=UserProfile(
            birthday=date(1990, 1, 1),
            goal="サブ3.5",
            runs_per_week=RunsPerWeek(min=3, max=5),
        ),
    )


def _make_plan() -> Plan:
    return Plan(
        week_start=date(2026, 3, 9),
        workout_evaluation="疲労は低め。",
        workouts=[
            WorkoutPlan(
                date=date(2026, 3, 9),
                workout_type="easy_run",
                purpose="疲労抜き",
                duration_min=40,
                intensity="low",
                max_hr=140,
                notes="リカバリージョグ",
            ),
        ],
        load_summary="軽めの週",
        reasoning="先週の疲労回復を優先。",
    )


SAMPLE_PLAN_JSON = json.dumps(
    {
        "week_start": "2026-03-09",
        "workout_evaluation": "疲労は低め。",
        "workouts": [
            {
                "date": "2026-03-09",
                "workout_type": "easy_run",
                "purpose": "疲労抜き",
                "duration_min": 40,
                "intensity": "low",
                "max_hr": 140,
                "notes": "リカバリージョグ",
            },
        ],
        "load_summary": "軽めの週",
        "reasoning": "先週の疲労回復を優先。",
    }
)

REVIEW_OK_RESPONSE = json.dumps({"result": "ok", "violations": [], "suggestions": []})
REVIEW_NG_RESPONSE = json.dumps(
    {
        "result": "ng",
        "violations": ["高強度セッションが多すぎます"],
        "suggestions": ["イージーランに変更"],
    }
)


def test_graph_compiles():
    """グラフがコンパイルできること。"""
    app = compile_graph()
    assert app is not None


def test_conditional_edge_ok():
    """review_result=='ok' で output_plan へルーティングされること。"""
    state = _make_state()
    state.review_result = "ok"
    state.review_retry_count = 1
    assert _should_continue(state) == "ok"


def test_conditional_edge_ng():
    """review_result=='ng' で generate_plan へルーティングされること。"""
    state = _make_state()
    state.review_result = "ng"
    state.review_retry_count = 1
    assert _should_continue(state) == "ng"


def test_conditional_edge_max_retries():
    """リトライ上限超過で 'ok'（強制終了）になること。"""
    state = _make_state()
    state.review_result = "ng"
    state.review_retry_count = planner.PLAN_REVIEW_MAX_RETRIES + 1
    assert _should_continue(state) == "ok"


def test_graph_full_flow(monkeypatch):
    """全ノードモック付きでSTART→END完走すること。"""

    def noop(state: AgentState) -> AgentState:
        return state

    def mock_generate_plan(state: AgentState) -> AgentState:
        state.plan = _make_plan()
        state.review_violations = []
        state.review_result = None
        return state

    def mock_self_check(state: AgentState) -> AgentState:
        state.review_result = "ok"
        state.review_retry_count += 1
        return state

    monkeypatch.setattr("run_coach.graph.fetch_workouts", noop)
    monkeypatch.setattr("run_coach.graph.fetch_races", noop)
    monkeypatch.setattr("run_coach.graph.fetch_calendar", noop)
    monkeypatch.setattr("run_coach.graph.fetch_weather", noop)
    monkeypatch.setattr("run_coach.planner.generate_plan", mock_generate_plan)
    monkeypatch.setattr("run_coach.graph.self_check", mock_self_check)
    monkeypatch.setattr("run_coach.graph.output_plan", noop)

    app = compile_graph()
    result = app.invoke(_make_state())

    assert result["review_result"] == "ok"
    assert result["plan"] is not None


def test_graph_retry_flow(monkeypatch):
    """NG→リトライ→OKのフローが動くこと。"""
    call_count = 0

    def noop(state: AgentState) -> AgentState:
        return state

    def mock_generate_plan(state: AgentState) -> AgentState:
        state.plan = _make_plan()
        state.review_violations = []
        state.review_result = None
        return state

    def mock_self_check(state: AgentState) -> AgentState:
        nonlocal call_count
        call_count += 1
        state.review_retry_count += 1
        if call_count == 1:
            state.review_result = "ng"
            state.review_violations = ["問題あり"]
        else:
            state.review_result = "ok"
            state.review_violations = []
        return state

    monkeypatch.setattr("run_coach.graph.fetch_workouts", noop)
    monkeypatch.setattr("run_coach.graph.fetch_races", noop)
    monkeypatch.setattr("run_coach.graph.fetch_calendar", noop)
    monkeypatch.setattr("run_coach.graph.fetch_weather", noop)
    monkeypatch.setattr("run_coach.planner.generate_plan", mock_generate_plan)
    monkeypatch.setattr("run_coach.graph.self_check", mock_self_check)
    monkeypatch.setattr("run_coach.graph.output_plan", noop)

    app = compile_graph()
    result = app.invoke(_make_state())

    assert result["review_result"] == "ok"
    assert call_count == 2  # 1回NG + 1回OK
