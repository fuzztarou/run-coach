from __future__ import annotations

import json
import os
from datetime import date, timedelta

from openai import OpenAI

from run_coach.state import AgentState, Plan

# デフォルトのLLMモデル（環境変数 LLM_MODEL で上書き可能）
DEFAULT_LLM_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """\
あなたは経験豊富なランニングコーチです。
選手のプロフィール、最近のワークアウト履歴、レース予測タイムを基に、
来週のトレーニング計画を作成してください。

以下の原則に従ってください:
- 漸進的過負荷: 週間走行距離の増加は10%以内
- ハード/イージーの交互配置
- 怪我の履歴を考慮し、無理のない計画にする
- 選手の目標レースペースを意識した練習を含める
- 休養日を適切に配置する
- ロング走など長時間のワークアウトは土日または祝日に配置する（平日は短めのメニューにする）

出力は以下のJSON形式のみで返してください（説明文は不要）:

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


def call_llm(prompt: str, system: str = "") -> str:
    """Call LLM with a prompt. Abstracted for future provider switching."""
    provider = os.environ.get("LLM_PROVIDER", "openai")

    if provider == "openai":
        client = OpenAI()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    raise ValueError(f"Unknown LLM provider: {provider}")


def _build_prompt(state: AgentState) -> str:
    """Build a user prompt from the current agent state."""
    profile = state.user_profile
    signals = state.signals

    parts = [
        "## 選手プロフィール",
        f"- 年齢: {profile.age}",
        f"- 目標: {profile.goal}",
        f"- 週間走行回数: {profile.runs_per_week.min}〜{profile.runs_per_week.max}回",
    ]

    if profile.injury_history:
        parts.append(f"- 怪我の履歴: {', '.join(profile.injury_history)}")

    if signals.race_predictions:
        parts.append("\n## レース予測タイム（Garmin推定）")
        parts.append("※VO2Maxベースの理論値であり、実際のレースタイムより速く出る傾向がある。過信せず参考値として扱うこと。")
        for dist, time_val in signals.race_predictions.items():
            parts.append(f"- {dist}: {time_val}")

    if signals.recent_workouts:
        parts.append("\n## 直近2週間のワークアウト")
        for w in signals.recent_workouts:
            hr_str = f", HR {w.avg_hr}" if w.avg_hr else ""
            te_str = f", TE {w.training_effect}" if w.training_effect else ""
            parts.append(
                f"- {w.date} | {w.type} | {w.distance_km}km | "
                f"{w.duration_min}min | {w.avg_pace}/km{hr_str}{te_str}"
            )

    next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    parts.append(f"\n来週の月曜日: {next_monday}")
    parts.append(f"週間走行回数の目安: {profile.runs_per_week.min}〜{profile.runs_per_week.max}回")
    parts.append("\n上記を踏まえて、来週のトレーニング計画をJSON形式で作成してください。")

    return "\n".join(parts)


def generate_plan(state: AgentState) -> AgentState:
    """Generate a weekly training plan using LLM."""
    prompt = _build_prompt(state)
    raw = call_llm(prompt, system=SYSTEM_PROMPT)

    data = json.loads(raw)
    state.plan = Plan(**data)
    return state
