from datetime import date

from run_coach.state import DailyWeather


def test_daily_weather_schema():
    """DailyWeatherが正しく生成できること"""
    w = DailyWeather(
        date=date(2026, 3, 10),
        temperature_max=18.5,
        temperature_min=8.2,
        precipitation_probability=30,
        precipitation_sum=0.5,
        wind_speed_max=15.3,
    )
    assert w.date == date(2026, 3, 10)
    assert w.temperature_max == 18.5
    assert w.precipitation_probability == 30


def test_daily_weather_minimal():
    """DailyWeatherの最小値が通ること"""
    w = DailyWeather(
        date=date(2026, 1, 1),
        temperature_max=0.0,
        temperature_min=-5.0,
        precipitation_probability=0,
        precipitation_sum=0.0,
        wind_speed_max=0.0,
    )
    assert w.precipitation_probability == 0
