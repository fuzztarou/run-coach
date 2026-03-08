from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date

from run_coach.state import AgentState, DailyWeather

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7
FORECAST_FIELDS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "precipitation_sum",
    "wind_speed_10m_max",
)


def _fetch_forecast(lat: float, lon: float) -> list[DailyWeather]:
    """Fetch 7-day weather forecast from Open-Meteo API."""
    params = (
        f"latitude={lat}&longitude={lon}"
        f"&daily={','.join(FORECAST_FIELDS)}"
        f"&forecast_days={FORECAST_DAYS}"
        "&timezone=auto"
    )
    url = f"{OPEN_METEO_URL}?{params}"

    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    daily = data["daily"]
    results: list[DailyWeather] = []
    for i in range(len(daily["time"])):
        results.append(
            DailyWeather(
                date=date.fromisoformat(daily["time"][i]),
                temperature_max=daily["temperature_2m_max"][i],
                temperature_min=daily["temperature_2m_min"][i],
                precipitation_probability=daily["precipitation_probability_max"][i],
                precipitation_sum=daily["precipitation_sum"][i],
                wind_speed_max=daily["wind_speed_10m_max"][i],
            )
        )
    return results


def fetch_weather(state: AgentState) -> AgentState:
    """Fetch weather forecast and populate state.constraints.weather."""
    location = state.user_profile.location
    if location is None:
        logger.info("locationが未設定のため天気予報をスキップします")
        return state

    try:
        forecasts = _fetch_forecast(location.latitude, location.longitude)
        state.constraints.weather = forecasts
    except Exception:
        logger.warning("天気予報の取得に失敗しました", exc_info=True)

    return state
