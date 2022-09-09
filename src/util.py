"""
Miscellaneous utility functions to be used in other parts of the program.

These functions are small and general enough that they don't warrant their own
module.

Functions:
    exit_critical_bare
    exit_critical
    market_time_to_utc
    utc_to_system_time
    plus_hour
    hours_contiguous
    pretty_datetime
"""

import sys
from datetime import datetime, timezone, timedelta
import time
import pytz

MARKET_TIMEZONE = pytz.timezone("Europe/Oslo")


def exit_critical_bare(message):
    """
    Same as exit_critical, but without logging the message. This should only be
    used before the logger is properly configured.
    """

    sys.exit(message)


def exit_critical(logger, message):
    """
    Log a critical error in the provided logger with give message, and then exit
    the program with a non-zero code with the same message.
    """

    logger.critical(message)
    sys.exit(message)


def market_time_to_utc(market_time: datetime) -> datetime:
    """
    Convert a time in the market's timezone to the equivalent time in UTC.
    """

    return MARKET_TIMEZONE.localize(market_time).astimezone(timezone.utc)


def utc_to_market_time(utc_time: datetime) -> datetime:
    """
    Convert a time in the market's timezone to the equivalent time in UTC.
    """

    return pytz.timezone("Etc/UTC").localize(utc_time).astimezone(MARKET_TIMEZONE)


def utc_to_system_time(utc_datetime: datetime) -> datetime:
    """
    Convert a datetime in UTC to the equivalent time in the systems local
    timezone.

    Note that is is a NAIVE conversion e.g. the datetime tzinfo is not modified.
    """

    system_utc_offset_secs = -[time.timezone, time.altzone][time.daylight]
    return utc_datetime + timedelta(seconds=system_utc_offset_secs)


def system_time_to_utc(sys_datetime: datetime) -> datetime:
    """
    Convert a datetime in UTC to the equivalent time in the systems local
    timezone.

    Note that is is a NAIVE conversion e.g. the datetime tzinfo is not modified.
    """

    utc_system_offset_secs = [time.timezone, time.altzone][time.daylight]
    return sys_datetime + timedelta(seconds=utc_system_offset_secs)


def plus_hour(date_time: datetime) -> datetime:
    """
    Add one hour to a datetime instance.
    """

    return date_time + timedelta(hours=1)


def hours_contiguous(first_start: datetime, second_start: datetime) -> bool:
    """
    Whether or not the hour that starts at first_start comes before and is
    contiguous with some amount of time starting at second_start.

    For example, if first_start is 01:00 and second_start is 02:00, this
    function would return true. If first_start were instead before 01:00, or
    after 2:00, this function would return false.
    """

    return first_start < second_start < first_start + timedelta(hours=1, minutes=1)


def pretty_datetime(date_time: datetime) -> str:
    """
    Given a datetime instance, return a string displaying it in an aesthetically
    pleasing way.

    All datetime fields are displayed except microseconds.
    """

    return date_time.strftime("%H:%M:%S %d/%m/%y")


def next_market_day_start() -> datetime:
    """
    Get the start of the next market day in market time.

    @return Start (00:00) of the next market day.
    """

    market_now = utc_to_market_time(system_time_to_utc(datetime.now()))
    return datetime(
        year=market_now.year, month=market_now.month, day=market_now.day
    ) + timedelta(days=1)


def get_21_30_market_as_sys() -> datetime:
    utc_21_30 = market_time_to_utc(
        datetime(year=1970, month=1, day=1, hour=21, minute=30, second=0)
    )
    return utc_to_system_time(utc_21_30)


def same_hour(a, b) -> bool:
    return (
        a != b
        and b - a < timedelta(minutes=60)
        and (b - timedelta(minutes=1)).hour == a.hour
    )
