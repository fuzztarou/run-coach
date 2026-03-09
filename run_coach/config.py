from __future__ import annotations

from pathlib import Path

import yaml

from run_coach.state import UserProfile

DEFAULT_CONFIG_PATH = Path("config/profile.yaml")
DEFAULT_SETTINGS_PATH = Path("config/settings.yaml")

DEFAULT_SETTINGS: dict[str, str | int] = {
    "llm_model": "gpt-4o-mini",
    "plan_review_max_retries": 2,
}


def load_profile(path: Path = DEFAULT_CONFIG_PATH) -> UserProfile:
    """Load user profile from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Copy config/profile.example.yaml to {path} and edit it."
        )
    data = yaml.safe_load(path.read_text())
    return UserProfile(**data)


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> dict[str, str | int]:
    """Load application settings from a YAML file.

    Returns default values if the file does not exist.
    """
    settings = dict(DEFAULT_SETTINGS)
    if path.exists():
        data = yaml.safe_load(path.read_text())
        if data:
            settings.update(data)
    return settings
