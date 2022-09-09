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

logger = log.LoggerLazyStatic("SCHEDULE")

ON = manage.EventType.ON
OFF = manage.EventType.OFF


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
                sched.append((ON, event.dt))
            else:
                # This is an OFF event
                sched.append((OFF, event.dt))
        if len(sched) > 0 and sched[0][0] == OFF:
            # First event is off, therefore we are currently on. Don't touch
            # the off event.
            sched.pop(0)
        return cls(sched)

    def __init__(
        self, sched: list[tuple[ScheduleBuilder.SwitchEvent, datetime.datetime]]
    ):
        self.sched = sched

    def add_heating_slice(self, start_time, num_mins):
        self.sched.append((ON, start_time))
        self.sched.append((OFF, start_time + datetime.timedelta(minutes=num_mins)))
        self.sort_schedule()
        self.clear_redundant_events()
        self.coalesce_fragments()

    def sort_schedule(self):
        self.sched = sorted(self.sched, key=lambda x: x[1])

    def clear_redundant_events(self):
        for i in reversed(range(len(self.sched) - 1)):
            if self.sched[i][1] == self.sched[i + 1][1]:
                self.sched.pop(i)
                self.sched.pop(i)

    def coalesce_fragments(self):
        for i in range(len(self.sched))[::-1][1::2]:
            this_on = self.sched[i][1]
            this_off = self.sched[i + 1][1]
            if util.same_hour(this_on, this_off):
                # This is a fragment
                if i > 0 and util.same_hour(self.sched[i - 1][1], this_on):
                    self.sched[i - 1] = (
                        OFF,
                        self.sched[i - 1][1] + (this_off - this_on),
                    )
                elif len(self.sched) - i > 3 and util.same_hour(
                    this_off, self.sched[i + 2][1]
                ):
                    self.sched[i + 2] = (
                        ON,
                        self.sched[i + 2][1] - (this_off - this_on),
                    )
                else:
                    continue
                self.sched.pop(i)
                self.sched.pop(i)

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
                "ON " if event_type == ON else "OFF",
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
        self.sort_schedule()
        self.display_schedule()

        # Sanity checks for safety
        if self.sched[0][0] != ON:
            raise Exception("Schedule doesn't start with ON event!")
        if self.sched[-1][0] != OFF:
            raise Exception("Schedule doesn't end with OFF event!")

        # Clear any switches scheduled for the same day
        manage.AtWrapper.clear_queue_from(
            prog_config["environment"]["switch_queue"], self.get_sched_day_start_utc()
        )

        # Upload switches
        for (event_type, event_time) in self.sched:
            manage.AtWrapper.add_switch_command(
                prog_config,
                "ON" if event_type == ON else "OFF",
                util.market_time_to_utc(event_time),
            )
