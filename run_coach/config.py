from __future__ import annotations

from pathlib import Path

import yaml

from run_coach.state import UserProfile

DEFAULT_CONFIG_PATH = Path("config/profile.yaml")
DEFAULT_SETTINGS_PATH = Path("config/settings.yaml")

DEFAULT_SETTINGS: dict[str, str | int | bool] = {
    "llm_model": "gpt-4o-mini",
    "plan_review_max_retries": 2,
    "debug": False,
    "db_port": 5433,
}


def load_profile(path: Path = DEFAULT_CONFIG_PATH) -> UserProfile:
    """Load user profile from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Copy config/profile.example.yaml to {path} and edit it."
        )
    data = yaml.safe_load(path.read_text())
    return UserProfile(**data)


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> dict[str, str | int | bool]:
    """Load application settings from a YAML file.

    Returns default values if the file does not exist.
    """
    settings = dict(DEFAULT_SETTINGS)
    if path.exists():
        data = yaml.safe_load(path.read_text())
        if data:
            settings.update(data)
    return settings


def apply_settings(settings: dict[str, str | int | bool]) -> None:
    """設定値を各モジュールに反映する。"""
    from run_coach.planner import set_plan_review_max_retries
    from run_coach.prompt import set_debug, set_llm_model

    set_llm_model(str(settings["llm_model"]))
    set_plan_review_max_retries(int(settings["plan_review_max_retries"]))
    set_debug(bool(settings.get("debug", False)))
