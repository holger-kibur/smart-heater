from datetime import datetime, timedelta
import pytest
from src import schedule, manage

ON = manage.EventType.ON
OFF = manage.EventType.OFF
MIN_OFFSETS = [0, 15, 30, 45]


def sort_schedule(sched):
    return sorted(sched, key=lambda x: x[1])


def get_datetime(hour, minute):
    hour = hour % 24
    day = (hour // 24) + 1
    return datetime(year=1970, month=1, day=day, hour=hour, minute=minute, second=0)


def assert_one_slice(builder, on_datetime, off_datetime):
    sorted_sched = sort_schedule(builder.sched)
    assert len(sorted_sched) == 2
    assert sorted_sched[0][0] == ON
    assert sorted_sched[1][0] == OFF
    assert sorted_sched[0][1] == on_datetime
    assert sorted_sched[1][1] == off_datetime


@pytest.mark.parametrize("hour", [0, 10, 23])
@pytest.mark.parametrize("minute", MIN_OFFSETS)
def test_schedule_single_hour(hour, minute):
    on_datetime = get_datetime(hour, minute)
    off_datetime = on_datetime + timedelta(hours=1)

    builder = schedule.ScheduleBuilder([])
    builder.add_heating_slice(on_datetime, 60)
    assert_one_slice(builder, on_datetime, off_datetime)


@pytest.mark.parametrize("hours", [2, 3])
@pytest.mark.parametrize("min_offset", MIN_OFFSETS)
def test_schedule_elide_following(hours, min_offset):
    on_datetime = get_datetime(0, min_offset)
    off_datetime = on_datetime + timedelta(hours=hours)

    builder = schedule.ScheduleBuilder([])
    for i in range(hours):
        builder.add_heating_slice(on_datetime + timedelta(hours=i), 60)
    assert_one_slice(builder, on_datetime, off_datetime)


@pytest.mark.parametrize("hours", [2, 3])
@pytest.mark.parametrize("min_offset", MIN_OFFSETS)
def test_schedule_elide_preceeding(hours, min_offset):
    off_datetime = get_datetime(24, min_offset)
    on_datetime = off_datetime - timedelta(hours=hours)

    builder = schedule.ScheduleBuilder([])
    for i in range(hours):
        builder.add_heating_slice(off_datetime - timedelta(hours=i + 1), 60)
    assert_one_slice(builder, on_datetime, off_datetime)


@pytest.mark.parametrize("min_offset", MIN_OFFSETS)
def test_schedule_elide_both(min_offset):
    on_datetime = get_datetime(0, min_offset)
    off_datetime = get_datetime(3, min_offset)

    builder = schedule.ScheduleBuilder([])
    builder.add_heating_slice(on_datetime, 60)
    builder.add_heating_slice(on_datetime + timedelta(hours=2), 60)
    builder.add_heating_slice(on_datetime + timedelta(hours=1), 60)
    assert_one_slice(builder, on_datetime, off_datetime)


@pytest.mark.parametrize("frag_len", MIN_OFFSETS[1:])
def test_schedule_frag_coalesce_preceeding(frag_len):
    frag_on = get_datetime(0, 0)
    block_on = get_datetime(1, 0)
    block_off = block_on + timedelta(hours=1)

    builder = schedule.ScheduleBuilder([])
    builder.add_heating_slice(frag_on, frag_len)
    builder.add_heating_slice(block_on, 60)
    assert_one_slice(builder, block_on - timedelta(minutes=frag_len), block_off)


@pytest.mark.parametrize("frag_len", MIN_OFFSETS[1:])
def test_schedule_frag_coalesce_following(frag_len):
    frag_on = get_datetime(1, 60 - frag_len)
    block_on = get_datetime(0, 0)

    builder = schedule.ScheduleBuilder([])
    builder.add_heating_slice(block_on, 60)
    builder.add_heating_slice(frag_on, frag_len)
    assert_one_slice(builder, block_on, block_on + timedelta(hours=1, minutes=frag_len))
