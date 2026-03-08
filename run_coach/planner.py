from __future__ import annotations

import json

from run_coach.prompt import COACHING_RULES, build_prompt, call_llm
from run_coach.state import AgentState, Plan

PLAN_REVIEW_MAX_RETRIES = 2

PLANNER_SYSTEM_PROMPT = (
    "あなたは経験豊富なランニングコーチです。\n"
    "選手のプロフィール、最近のワークアウト履歴、レース予測タイム、\n"
    "大会情報、カレンダー、天気予報を基に、指定された期間のトレーニング計画を作成してください。\n"
    "\n"
    "## コーチングルール（必ず守ること）\n"
    "\n"
    f"{COACHING_RULES}\n"
    "\n"
    """出力は以下のJSON形式のみで返してください（説明文は不要）:

{
  "week_start": "YYYY-MM-DD",
  "workout_evaluation": "直近のワークアウト履歴を評価し、疲労度・トレーニング効果・改善点を日本語で簡潔にまとめる",
  "workouts": [
    {
      "date": "YYYY-MM-DD",
      "workout_type": "easy_run | tempo | intervals | long_run | cross_training",
      "purpose": "このワークアウトの目的（例: 疲労抜き、心肺強化、有酸素ベース構築、閾値向上）",
      "duration_min": 整数,
      "intensity": "low | moderate | high",
      "max_hr": "このワークアウト中の心拍上限（整数）。選手の年齢から推定最大心拍数を算出し、目的に応じた適切な上限を設定。restの場合はnull",
      "notes": "日本語で簡潔に"
    }
  ],
  "load_summary": "今週の負荷の概要（日本語）",
  "reasoning": "この計画の根拠（日本語）"
}
"""
)


def generate_plan_with_review(state: AgentState) -> AgentState:
    """generate_plan + review_plan をリトライ付きで実行する。"""
    from run_coach.plan_review import review_plan

    state = generate_plan(state)
    state = review_plan(state)

    retries = 0
    while state.review_result == "ng" and retries < PLAN_REVIEW_MAX_RETRIES:
        retries += 1
        violations = state.review_violations
        state.review_result = None
        state.review_violations = []
        state = generate_plan(state, feedback=violations)
        state = review_plan(state)

    return state


def generate_plan(state: AgentState, feedback: list[str] | None = None) -> AgentState:
    """Generate a weekly training plan using LLM."""
    prompt = build_prompt(state)
    if feedback:
        prompt += "\n\n## 前回のプランで指摘された問題\n"
        prompt += "\n".join(f"- {v}" for v in feedback)
        prompt += "\n\nこれらの問題を修正した計画を作成してください。"

    raw = call_llm(prompt, system=PLANNER_SYSTEM_PROMPT)

    data = json.loads(raw)
    state.plan = Plan(**data)
    return state
