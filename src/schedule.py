"""
Tools that can be used to create a minimized schedule for time-slices, and
upload it to the system in a series of "at" commands.

Classes:
    AtCmdWrapper
    ScheduleBuilder
"""

import datetime
import os
import subprocess

from . import log, util

logger = log.LoggerFactory.get_logger("SCHEDULE")


class AtCmdWrapper():
    """
    Namespacing class to wrap around functions which interact with the "at"
    daemon. Also contains a testing hook that intercepts commands
    to-be-uploaded.
    """

    test_hook_cmd = None

    @staticmethod
    def datetime_to_at(time: datetime.datetime) -> str:
        """
        Convert a datetime instance to an "at" command with that exact time
        specified with the -t flag.
        """

        systime = util.utc_to_system_time(time)
        # Disable linter warning because making this an f-string would make the
        # line unbearably long.
        # pylint: disable=consider-using-f-string
        return "{:0>4}{:0>2}{:0>2}{:0>2}{:0>2}".format(
            systime.year,
            systime.month,
            systime.day,
            systime.hour,
            systime.minute)

    @classmethod
    def upload_command(cls, prog_config, event_type, event_time):
        """
        Transform an on/off command into an "at" command to run the
        turn_on/turn_off scripts, and upload the command to the "at" daemon.
        """

        # This would be exceedingly ugly with f-string
        # pylint: disable=consider-using-f-string
        event_cmd = "echo \"{} {}/switch.py -c {} -a {}\"".format(
            prog_config['environment']['python'],
            os.getcwd(),
            prog_config.source_file,
            'ON' if event_type == ScheduleBuilder.ON_EVENT else 'OFF',
        )
        event_cmd += f" | at -q {prog_config['environment']['at_queue']}"
        event_cmd += f" -t {cls.datetime_to_at(event_time)}"

        logger.debug("upload command: %s", event_cmd)
        if cls.test_hook_cmd is None:
            subprocess.call(event_cmd, shell=True)
        else:
            # Disable linter warning because it is None checked, and is
            # dynamically updated for testing.
            cls.test_hook_cmd( # pylint: disable=not-callable
                event_type, event_cmd)


class ScheduleBuilder():
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

    ON_EVENT = 0
    OFF_EVENT = 1

    def __init__(self):
        self.sched = []

    def add_heating_slice(self, start_time, num_mins):
        """
        Add some number of minutes of heating within the hour starting at
        start_time to the schedule.

        This function upholds the condition of string on/off event interleaving.
        This means that after each insertion, there will be no such case that
        the same event type can occur twice in a row chronologically.

        The events in the schedule are not necessarily in chronological order,
        but they can be sorted using the standard library function, due to the
        string interleaving condition.

        It's important that there be only one non-60 minute time-slice, and that
        it be the last one to be added.
        """

        for i, (event_type, event_time) in enumerate(self.sched):
            if util.hours_contiguous(start_time, event_time):
                if event_type == self.ON_EVENT:
                    self.sched[i] = (
                        self.ON_EVENT,
                        self.sched[i][1] - datetime.timedelta(minutes=num_mins))
                    break
                # If this time slice comes directly before an OFF event,
                # then we have a duplicate entry.
                raise Exception(
                    "Duplicate entry in scheduler: slice comes before OFF!")
            if util.hours_contiguous(event_time, util.plus_hour(start_time)):
                if event_type == self.OFF_EVENT:
                    self.sched[i] = (
                        self.OFF_EVENT,
                        self.sched[i][1] + datetime.timedelta(minutes=num_mins))
                    break
                # If this time slice comes directly after an ON event, then
                # we also have a duplicate entry.
                raise Exception(
                    "Duplicate entry in scheduler: slice comes after ON!")
        else:
            self.sched.append((self.ON_EVENT, start_time))
            self.sched.append((self.OFF_EVENT, start_time +
                              datetime.timedelta(minutes=num_mins)))

    def display_schedule(self):
        """
        Pretty-print the current schedule to the logger as info messages.
        """

        logger.info("-" * 69)
        logger.info(
            "| EVENT |    MARKET TIME    |     UTC TIME      |    SYSTEM TIME    |")
        for (event_type, event_time) in self.sched:
            utc_time = util.market_time_to_utc(event_time)
            sys_time = util.utc_to_system_time(utc_time)
            logger.info("|  %s  | %s | %s | %s |",
                        "ON " if event_type == self.ON_EVENT else "OFF",
                        util.pretty_datetime(event_time),
                        util.pretty_datetime(utc_time),
                        util.pretty_datetime(sys_time),
                        )
        logger.info("-" * 69)

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

        for (event_type, event_time) in self.sched:
            AtCmdWrapper.upload_command(
                prog_config, event_type, util.market_time_to_utc(event_time))
