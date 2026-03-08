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
選手のプロフィール、最近のワークアウト履歴、レース予測タイム、
大会情報、カレンダー、天気予報を基に、指定された期間のトレーニング計画を作成してください。

## コーチングルール（必ず守ること）

1. 高強度セッション（tempo, intervals）は週2回まで
2. ロング走の翌日は必ずイージーランまたは休養
3. 週間走行距離の増加は前週比10%以内
4. レース3週間前からテーパリング開始（走行距離を段階的に減らす）
5. HRV低下 + 睡眠不良の場合はリカバリー優先
6. 降水確率60%以上の日は室内トレや代替メニューを提案
7. カレンダーで予定が多い日にはワークアウトを入れない
8. ロング走は土日または祝日に配置する（平日は短めのメニューにする）

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
        parts.append(
            "※VO2Maxベースの理論値であり、実際のレースタイムより速く出る傾向がある。過信せず参考値として扱うこと。"
        )
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

    constraints = state.constraints

    if constraints.races:
        parts.append("\n## 大会情報")
        for r in constraints.races:
            primary = " ★メインレース" if r.is_primary else ""
            dist = f" {r.distance_km}km" if r.distance_km else ""
            goal = ""
            if r.goal_time_seconds:
                h = int(r.goal_time_seconds // 3600)
                m = int((r.goal_time_seconds % 3600) // 60)
                goal = f" 目標: {h}:{m:02d}"
            parts.append(f"- {r.date} | {r.event_name}{dist}{goal}{primary}")

    if constraints.available_slots:
        parts.append("\n## カレンダー（今後7日間）")
        for slot in constraints.available_slots:
            if slot.available:
                parts.append(f"- {slot.date}: 空き")
            else:
                parts.append(f"- {slot.date}: {' / '.join(slot.events)}")

    if constraints.weather:
        parts.append("\n## 天気予報（今後7日間）")
        for w in constraints.weather:
            parts.append(
                f"- {w.date}: {w.temperature_min}〜{w.temperature_max}℃, "
                f"降水確率{w.precipitation_probability}%, "
                f"降水量{w.precipitation_sum}mm, "
                f"風速{w.wind_speed_max}km/h"
            )

    today = date.today()
    # 今日既にワークアウト済みなら明日から、そうでなければ今日から計画開始
    today_has_workout = any(w.date == today for w in signals.recent_workouts)
    plan_start = today + timedelta(days=1) if today_has_workout else today
    # 次の日曜日まで（plan_startが日曜なら当日含め7日間）
    days_until_sunday = (6 - plan_start.weekday()) % 7 or 7
    plan_end = plan_start + timedelta(days=days_until_sunday)

    parts.append(f"\n今日の日付: {today}")
    if today_has_workout:
        parts.append("※ 今日は既にワークアウト済みです。")
    parts.append(f"計画期間: {plan_start} 〜 {plan_end}")
    parts.append(
        f"週間走行回数の目安: {profile.runs_per_week.min}〜{profile.runs_per_week.max}回"
    )
    parts.append(
        "\n上記を踏まえて、指定された計画期間のトレーニング計画をJSON形式で作成してください。"
    )
    parts.append(
        "注意: 計画期間の初日や翌日にワークアウトを入れることは必須ではありません。"
        "直近の疲労度やカレンダーを考慮し、休養日を含め最適なスケジュールを組んでください。"
    )

    return "\n".join(parts)


def generate_plan(state: AgentState) -> AgentState:
    """Generate a weekly training plan using LLM."""
    prompt = _build_prompt(state)
    raw = call_llm(prompt, system=SYSTEM_PROMPT)

    data = json.loads(raw)
    state.plan = Plan(**data)
    return state
