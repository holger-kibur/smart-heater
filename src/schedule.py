"""
Tools that can be used to create a minimized schedule for time-slices, and
upload it to the system in a series of "at" commands.

Classes:
    AtCmdWrapper
    ScheduleBuilder
"""
from __future__ import annotations

import datetime
from typing import TypeVar

from . import log, util, manage

logger = log.LoggerFactory.get_logger("SCHEDULE")


class ScheduleBuilder:
    """
    A stateful class for building a schedule from heating time-slices.

    A heating time-slice is a specified number of heating minutes in a specific
    hour. If a time-slice is provided with less than 60 minutes of heating, then
    that incomplete hour is free to be shifted to either side of the hour e.g.
    starting from XX:00, or ending on XX:59.

    This builder seeks to minimize the number of on/off events that happen in
    the schedule by combining adjacent and contiguous time slices, thereby
    removing a set of on/off events. This is useful for prolonging the life of
    relays, for example.
    """

    SwitchEvent = TypeVar("SwitchEvent")
    ON_EVENT = 0
    OFF_EVENT = 1

    @classmethod
    def retrieve_sched(cls, prog_config):
        sched = []
        for i, event in enumerate(
            sorted(
                list(
                    manage.AtQueueMember.from_queue(
                        prog_config["environment"]["switch_queue"]
                    )
                ),
                key=lambda x: x.dt,
            )
        ):
            if i % 2 == 0:
                # This is an ON event
                sched.append((cls.ON_EVENT, event.dt))
            else:
                # This is an OFF event
                sched.append((cls.OFF_EVENT, event.dt))
        if len(sched) > 0 and sched[0][0] == cls.OFF_EVENT:
            # First event is off, therefore we are currently on. Don't touch
            # the off event.
            sched.pop(0)
        return cls(sched)

    def __init__(
        self, sched: list[tuple[ScheduleBuilder.SwitchEvent, datetime.datetime]]
    ):
        self.sched = sched

    def add_heating_slice(self, start_time, num_mins):
        """
        Add some number of minutes of heating within the hour starting at
        start_time to the schedule.

        This function upholds the condition of strict on/off event interleaving.
        This means that after each insertion, there will be no such case that
        the same event type can occur twice in a row chronologically.

        The events in the schedule are not necessarily in chronological order,
        but they can be sorted using the standard library function, due to the
        strict interleaving condition.

        It's important that there be only one non-60 minute time-slice, and that
        it be the last one to be added.
        """

        for i, (event_type, event_time) in enumerate(self.sched):
            if util.hours_contiguous(start_time, event_time):
                if event_type == self.ON_EVENT:
                    self.sched[i] = (
                        self.ON_EVENT,
                        self.sched[i][1] - datetime.timedelta(minutes=num_mins),
                    )
                    break
                # If this time slice comes directly before an OFF event,
                # then we have a duplicate entry.
                raise Exception("Duplicate entry in scheduler: slice comes before OFF!")
            if util.hours_contiguous(event_time, util.plus_hour(start_time)):
                if event_type == self.OFF_EVENT:
                    self.sched[i] = (
                        self.OFF_EVENT,
                        self.sched[i][1] + datetime.timedelta(minutes=num_mins),
                    )
                    break
                # If this time slice comes directly after an ON event, then
                # we also have a duplicate entry.
                raise Exception("Duplicate entry in scheduler: slice comes after ON!")
        else:
            self.sched.append((self.ON_EVENT, start_time))
            self.sched.append(
                (self.OFF_EVENT, start_time + datetime.timedelta(minutes=num_mins))
            )

    def display_schedule(self):
        """
        Pretty-print the current schedule to the logger as info messages.
        """

        logger.info("-" * 69)
        logger.info(
            "| EVENT |    MARKET TIME    |     UTC TIME      |    SYSTEM TIME    |"
        )
        for (event_type, event_time) in self.sched:
            utc_time = util.market_time_to_utc(event_time)
            sys_time = util.utc_to_system_time(utc_time)
            logger.info(
                "|  %s  | %s | %s | %s |",
                "ON " if event_type == self.ON_EVENT else "OFF",
                util.pretty_datetime(event_time),
                util.pretty_datetime(utc_time),
                util.pretty_datetime(sys_time),
            )
        logger.info("-" * 69)

    def get_sched_day_start_utc(self) -> datetime.datetime:
        """
        Get start time of the day in which times are currently scheduled.

        @return Day start time (00:00) in UTC.
        """

        if len(self.sched) == 0:
            raise Exception("Can't get schedule day start with an empty schedule!")
        tmrw_first_time = self.sched[0][1]
        tmrw_midnight = datetime.datetime(
            year=tmrw_first_time.year,
            month=tmrw_first_time.month,
            day=tmrw_first_time.day,
        )
        return util.market_time_to_utc(tmrw_midnight)

    def upload(self, prog_config):
        """
        Upload the current schedule to the system "at" daemon to be ran.

        Create an "at" command for each event in the schedule that calls the
        turn_on or turn_off scripts depending on event type.

        This function also passively chronologically sorts self.sched, which
        doesn't make any functional difference due to the string on/off
        interleaving condition.
        """

        if len(self.sched) == 0:
            return
        self.sched = sorted(self.sched, key=lambda x: x[1])
        self.display_schedule()

        # Sanity checks for safety
        if self.sched[0][0] != self.ON_EVENT:
            raise Exception("Schedule doesn't start with ON event!")
        if self.sched[-1][0] != self.OFF_EVENT:
            raise Exception("Schedule doesn't end with OFF event!")

        # Clear any switches scheduled for the same day
        manage.AtWrapper.clear_queue_from(
            prog_config["environment"]["switch_queue"], self.get_sched_day_start_utc()
        )

        # Upload switches
        for (event_type, event_time) in self.sched:
            manage.AtWrapper.add_switch_command(
                prog_config,
                "ON" if event_type == self.ON_EVENT else "OFF",
                util.market_time_to_utc(event_time),
            )
