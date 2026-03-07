from __future__ import annotations

from pathlib import Path

import yaml

from run_coach.state import UserProfile

DEFAULT_CONFIG_PATH = Path("config/profile.yaml")


def load_profile(path: Path = DEFAULT_CONFIG_PATH) -> UserProfile:
    """Load user profile from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Copy config/profile.example.yaml to {path} and edit it."
        )
    data = yaml.safe_load(path.read_text())
    return UserProfile(**data)
