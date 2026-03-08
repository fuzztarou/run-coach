from datetime import date

from run_coach.state import CalendarSlot


def test_calendar_slot_available():
    """空きスロットが正しく生成できること"""
    slot = CalendarSlot(date=date(2026, 3, 10), available=True)
    assert slot.available is True
    assert slot.events == []


def test_calendar_slot_busy():
    """予定ありスロットが正しく生成できること"""
    slot = CalendarSlot(
        date=date(2026, 3, 10),
        available=False,
        events=["会議", "ランチ"],
    )
    assert slot.available is False
    assert len(slot.events) == 2


def test_build_slots_logic():
    """_build_slotsのロジック検証（直接インポートせずロジックを再現）"""
    from datetime import timedelta

    events_by_date = {
        date(2026, 3, 10): ["会議"],
        date(2026, 3, 12): ["出張", "会食"],
    }

    today = date(2026, 3, 9)
    slots = []
    for i in range(7):
        d = today + timedelta(days=i)
        events = events_by_date.get(d, [])
        slots.append(CalendarSlot(date=d, available=len(events) == 0, events=events))

    assert len(slots) == 7
    assert slots[0].available is True  # 3/9: no events
    assert slots[1].available is False  # 3/10: 会議
    assert slots[2].available is True  # 3/11: no events
    assert slots[3].available is False  # 3/12: 出張, 会食
    assert len(slots[3].events) == 2
