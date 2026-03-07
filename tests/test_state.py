from datetime import date

from run_coach.state import UserProfile


def test_age_computed_from_birthday():
    """birthdayからageが正しく計算されること"""
    p = UserProfile(
        birthday=date(1991, 5, 10), goal="サブ4", runs_per_week={"min": 3, "max": 4}
    )
    expected = (
        date.today().year - 1991 - ((date.today().month, date.today().day) < (5, 10))
    )
    assert p.age == expected
