"""ペース等の単位変換ユーティリティ。"""

from __future__ import annotations


def pace_str_to_seconds(pace: str) -> float:
    """ペース文字列 "5:30" を秒/km (330.0) に変換する。"""
    parts = pace.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def pace_seconds_to_str(duration_sec: float, distance_km: float) -> str:
    """ラップタイム(秒)と距離(km)からペース文字列 "M:SS" に変換する。"""
    if distance_km <= 0:
        return "0:00"
    pace_s_per_km = duration_sec / distance_km
    pace_min = int(pace_s_per_km // 60)
    pace_sec = int(pace_s_per_km % 60)
    return f"{pace_min}:{pace_sec:02d}"
