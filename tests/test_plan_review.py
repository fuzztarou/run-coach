import json
from datetime import date

from run_coach.state import (
    AgentState,
    Plan,
    UserProfile,
    RunsPerWeek,
    WorkoutPlan,
)
from run_coach.plan_review import review_plan
from run_coach.planner import generate_plan_with_review


def _make_state() -> AgentState:
    """テスト用の基本的なAgentStateを作成する。"""
    return AgentState(
        user_profile=UserProfile(
            birthday=date(1990, 1, 1),
            goal="サブ3.5",
            runs_per_week=RunsPerWeek(min=3, max=5),
        ),
    )


def _make_plan() -> Plan:
    """テスト用のプランを作成する。"""
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
            WorkoutPlan(
                date=date(2026, 3, 11),
                workout_type="tempo",
                purpose="閾値向上",
                duration_min=50,
                intensity="high",
                max_hr=165,
                notes="テンポ走",
            ),
        ],
        load_summary="軽めの週",
        reasoning="先週の疲労回復を優先。",
    )


REVIEW_OK_RESPONSE = json.dumps({"result": "ok", "violations": [], "suggestions": []})

REVIEW_NG_RESPONSE = json.dumps(
    {
        "result": "ng",
        "violations": ["高強度セッションが週3回あり、上限の2回を超えています"],
        "suggestions": ["水曜のインターバルをイージーランに変更してください"],
    }
)


def test_review_plan_ok(monkeypatch):
    """ルール準拠のプランがOK判定されること。"""
    state = _make_state()
    state.plan = _make_plan()

    monkeypatch.setattr(
        "run_coach.plan_review.call_llm",
        lambda prompt, system="": REVIEW_OK_RESPONSE,
    )

    state = review_plan(state)

    assert state.review_result == "ok"
    assert state.review_violations == []


def test_review_plan_ng(monkeypatch):
    """ルール違反のプランがNG判定されること。"""
    state = _make_state()
    state.plan = _make_plan()

    monkeypatch.setattr(
        "run_coach.plan_review.call_llm",
        lambda prompt, system="": REVIEW_NG_RESPONSE,
    )

    state = review_plan(state)

    assert state.review_result == "ng"
    assert len(state.review_violations) == 1
    assert "高強度" in state.review_violations[0]


def test_review_plan_no_plan():
    """プランがない場合はNG判定されること。"""
    state = _make_state()
    state = review_plan(state)

    assert state.review_result == "ng"
    assert "プランが生成されていません" in state.review_violations


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


def test_generate_plan_with_review_retries(monkeypatch):
    """NG→再生成→OKのフローが動くこと。"""
    call_count = 0

    def mock_call_llm(prompt: str, system: str = "") -> str:
        nonlocal call_count
        call_count += 1
        # 奇数回はgenerate_plan、偶数回はreview_plan
        if call_count % 2 == 1:
            return SAMPLE_PLAN_JSON
        if call_count == 2:
            return REVIEW_NG_RESPONSE
        return REVIEW_OK_RESPONSE

    monkeypatch.setattr("run_coach.plan_review.call_llm", mock_call_llm)
    monkeypatch.setattr("run_coach.planner.call_llm", mock_call_llm)

    state = _make_state()
    state = generate_plan_with_review(state)

    assert state.review_result == "ok"
    assert state.plan is not None
    # 初回生成 + 初回レビュー(NG) + 再生成 + 再レビュー(OK) = 4回
    assert call_count == 4


def test_generate_plan_with_review_max_retries(monkeypatch):
    """リトライ上限に達したら最後のプランを返すこと。"""
    call_count = 0

    def mock_call_llm(prompt: str, system: str = "") -> str:
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:
            return SAMPLE_PLAN_JSON
        return REVIEW_NG_RESPONSE  # 常にNG

    monkeypatch.setattr("run_coach.plan_review.call_llm", mock_call_llm)
    monkeypatch.setattr("run_coach.planner.call_llm", mock_call_llm)

    state = _make_state()
    state = generate_plan_with_review(state)

    assert state.review_result == "ng"
    assert state.plan is not None
    # 初回 + 2リトライ = 3回生成 + 3回レビュー = 6回
    assert call_count == 6


def test_violations_passed_to_regeneration(monkeypatch):
    """再生成時にviolationsがプロンプトに含まれること。"""
    call_count = 0
    captured_prompts: list[str] = []

    def mock_call_llm(prompt: str, system: str = "") -> str:
        nonlocal call_count
        call_count += 1
        captured_prompts.append(prompt)
        if call_count % 2 == 1:
            return SAMPLE_PLAN_JSON
        if call_count == 2:
            return REVIEW_NG_RESPONSE
        return REVIEW_OK_RESPONSE

    monkeypatch.setattr("run_coach.plan_review.call_llm", mock_call_llm)
    monkeypatch.setattr("run_coach.planner.call_llm", mock_call_llm)

    state = _make_state()
    state = generate_plan_with_review(state)

    # 3番目のプロンプト（再生成時）にviolationsが含まれること
    regeneration_prompt = captured_prompts[2]
    assert "前回のプランで指摘された問題" in regeneration_prompt
    assert "高強度セッションが週3回あり" in regeneration_prompt
