import json
from datetime import date

from run_coach.state import Plan


SAMPLE_LLM_OUTPUT = json.dumps({
    "week_start": "2026-03-09",
    "workout_evaluation": "疲労は低め。負荷を上げる余地がある。",
    "workouts": [
        {
            "date": "2026-03-09",
            "workout_type": "easy_run",
            "purpose": "疲労抜き",
            "duration_min": 40,
            "intensity": "low",
            "max_hr": 140,
            "notes": "リカバリージョグ"
        },
        {
            "date": "2026-03-11",
            "workout_type": "tempo",
            "purpose": None,
            "duration_min": None,
            "intensity": None,
            "max_hr": 165,
            "notes": ""
        },
    ],
    "load_summary": "軽めの週",
    "reasoning": "先週の疲労回復を優先。"
})


def test_plan_from_llm_output():
    """LLMのJSON出力がPlanスキーマにパースできること（null含む）"""
    data = json.loads(SAMPLE_LLM_OUTPUT)
    plan = Plan(**data)

    assert plan.week_start == date(2026, 3, 9)
    assert len(plan.workouts) == 2
    assert plan.workouts[0].workout_type == "easy_run"
    assert plan.workouts[1].purpose is None  # LLMがnullを返すケース
