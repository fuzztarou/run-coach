from __future__ import annotations

import os
from datetime import date, timedelta

from openai import OpenAI

from run_coach.state import AgentState

# デフォルトのLLMモデル（環境変数 LLM_MODEL で上書き可能）
DEFAULT_LLM_MODEL = "gpt-4o-mini"

COACHING_RULES = """\
1. 高強度セッション（tempo, intervals）は週2回まで
2. ロング走の翌日は必ずイージーランまたは休養
3. 週間走行距離の増加は前週比10%以内
4. レース3週間前からテーパリング開始（走行距離を段階的に減らす）
5. HRV低下 + 睡眠不良の場合はリカバリー優先
6. 降水確率60%以上の日は室内トレや代替メニューを提案
7. カレンダーで予定が多い日にはワークアウトを入れない
8. ロング走は土日または祝日に配置する（平日は短めのメニューにする）
9. 週間ワークアウト回数は選手の設定した上限（runs_per_week.max）を超えないこと"""


def call_llm(prompt: str, system: str = "") -> str:
    """Call LLM with a prompt. Abstracted for future provider switching."""
    provider = os.environ.get("LLM_PROVIDER", "openai")

    if provider == "openai":
        client = OpenAI()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(  # type: ignore[call-overload]
            model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    raise ValueError(f"Unknown LLM provider: {provider}")


def build_prompt(state: AgentState) -> str:
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
        for day_weather in constraints.weather:
            parts.append(
                f"- {day_weather.date}: {day_weather.temperature_min}〜{day_weather.temperature_max}℃, "
                f"降水確率{day_weather.precipitation_probability}%, "
                f"降水量{day_weather.precipitation_sum}mm, "
                f"風速{day_weather.wind_speed_max}km/h"
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
