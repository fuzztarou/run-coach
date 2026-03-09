from __future__ import annotations

import json

from run_coach.prompt import COACHING_RULES, build_prompt, call_llm, is_debug
from run_coach.state import AgentState

PLAN_REVIEW_SYSTEM_PROMPT = (
    "あなたはランニングコーチの品質チェッカーです。\n"
    "以下のコーチングルールに基づいて、生成されたトレーニング計画を検証してください。\n"
    "\n"
    "## コーチングルール\n"
    "\n"
    f"{COACHING_RULES}\n"
    "\n"
    """## 検証方法

計画の各ワークアウトについて、上記ルールへの違反がないか確認してください。

出力は以下のJSON形式のみで返してください（説明文は不要）:

{
  "result": "ok" または "ng",
  "violations": ["違反内容1", "違反内容2", ...],
  "suggestions": ["改善提案1", "改善提案2", ...]
}

- 違反がなければ result を "ok" にし、violations は空配列にしてください。
- 違反がある場合は result を "ng" にし、具体的な違反内容を violations に記載してください。
"""
)


def self_check(state: AgentState) -> AgentState:
    """LangGraphノード: プランレビュー + リトライカウンター更新。"""
    print("プランをセルフチェック中...")
    state = review_plan(state)
    state.review_retry_count += 1
    return state


def review_plan(state: AgentState) -> AgentState:
    """LLMでプランを検証し、結果をstateに記録する。"""
    if state.plan is None:
        state.review_result = "ng"
        state.review_violations = ["プランが生成されていません"]
        return state

    plan_json = state.plan.model_dump_json(indent=2)
    prompt_parts = [
        build_prompt(state),
        "\n## 生成されたトレーニング計画\n",
        plan_json,
        "\n上記の計画をコーチングルールに基づいて検証してください。",
    ]
    prompt = "\n".join(prompt_parts)

    raw = call_llm(prompt, system=PLAN_REVIEW_SYSTEM_PROMPT)
    data = json.loads(raw)

    state.review_result = data.get("result", "ng")
    state.review_violations = data.get("violations", [])
    if is_debug():
        print(f"\n[DEBUG] レビュー結果: {state.review_result}")
        if state.review_violations:
            print("[DEBUG] 指摘事項:")
            for violation in state.review_violations:
                print(f"  - {violation}")
    return state
