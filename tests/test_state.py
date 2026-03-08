from datetime import date

import pytest
from pydantic import ValidationError

from run_coach.state import AgentState, Constraints, Location, UserProfile


def test_age_computed_from_birthday():
    """birthdayからageが正しく計算されること"""
    p = UserProfile(
        birthday=date(1991, 5, 10), goal="サブ4", runs_per_week={"min": 3, "max": 4}
    )
    expected = (
        date.today().year - 1991 - ((date.today().month, date.today().day) < (5, 10))
    )
    assert p.age == expected


def test_location_valid():
    """有効な緯度・経度でLocationが生成できること"""
    loc = Location(latitude=35.6762, longitude=139.6503)
    assert loc.latitude == 35.6762
    assert loc.longitude == 139.6503


def test_location_invalid_latitude():
    """範囲外の緯度でValidationErrorが発生すること"""
    with pytest.raises(ValidationError):
        Location(latitude=91.0, longitude=0.0)


def test_user_profile_without_location():
    """locationなしのUserProfileが後方互換で動くこと"""
    p = UserProfile(
        birthday=date(1990, 1, 1), goal="サブ3.5", runs_per_week={"min": 4, "max": 5}
    )
    assert p.location is None


def test_user_profile_with_location():
    """locationありのUserProfileが正しく動くこと"""
    p = UserProfile(
        birthday=date(1990, 1, 1),
        goal="サブ3.5",
        runs_per_week={"min": 4, "max": 5},
        location={"latitude": 35.6762, "longitude": 139.6503},
    )
    assert p.location is not None
    assert p.location.latitude == 35.6762


def test_agent_state_default_constraints():
    """AgentStateのconstraintsがデフォルトで空Constraintsになること"""
    state = AgentState(
        user_profile=UserProfile(
            birthday=date(1990, 1, 1),
            goal="サブ4",
            runs_per_week={"min": 3, "max": 4},
        )
    )
    assert isinstance(state.constraints, Constraints)
    assert state.constraints.races == []
    assert state.constraints.weather == []
    assert state.constraints.available_slots == []
