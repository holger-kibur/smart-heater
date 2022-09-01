"""
Module to encapsulate all the program's interaction with operating system daemons.

The daemons used are 'at' and 'crontab'.
"""
from __future__ import annotations

import subprocess
import io
from datetime import datetime
import pid
import crontab

from src import util, config

FETCH_CRON_COMMENT = "smart-heater-fetch"
PIDFILE_NAME = "smart-heater"


class EventType:
    ON = 1
    OFF = 0


class AtQueueMember:
    """
    Utility class for representing scheduled jobs in the 'at' daemon queue.
    This class only parses and stores fields necessary for program function.
    """

    @classmethod
    def from_queue(cls, queue: str) -> list[AtQueueMember]:
        at_queue = io.BytesIO(subprocess.check_output(["at", "-l"]))
        members = []
        for member_line in at_queue:
            member = AtQueueMember.from_queue_line(member_line.decode("UTF-8"))
            if member.queue == queue:
                members.append(member)
        members = sorted(members, key=lambda x: x.dt)
        for i, member in enumerate(reversed(members)):
            if i % 2 == 0:
                member.action = EventType.OFF
            else:
                member.action = EventType.ON
        return members

    @classmethod
    def from_queue_line(cls, queue_member_str):
        fields = queue_member_str.split()
        return cls(
            int(fields[0]),
            util.system_time_to_utc(
                datetime.strptime(" ".join(fields[1:6]), "%a %b %d %H:%M:%S %Y")
            ),
            fields[6],
            None,
        )

    def __init__(self, id, dt, queue, action):
        self.id = id
        self.dt = dt
        self.queue = queue
        self.action = action

    def is_equivalent(self, other):
        return (
            self.dt == other.dt
            and self.queue == other.queue
            and self.action == other.action
        )


class AtWrapper:
    """
    Namespacing class for encapsulating interactions with the 'at' daemon.
    """

    @staticmethod
    def datetime_to_at(time: datetime) -> str:
        """
        Convert a datetime instance to an "at" command with that exact time
        specified with the -t flag. The datetime passed to this method must be
        in UTC, which it then converts to system time.

        @param time Time to-be-converted in UTC.

        @return Acceptable -t flag timestamp.
        """

        systime = util.utc_to_system_time(time)
        return "{:0>4}{:0>2}{:0>2}{:0>2}{:0>2}".format(
            systime.year, systime.month, systime.day, systime.hour, systime.minute
        )

    @classmethod
    def clear_queue_from(cls, queue: str, dt: datetime):
        """
        Remove all members in the 'at' daemon queue starting on and coming
        after a specific datetime.

        @param queue Single character string for which queue to clear. @param
        dt Datetime on and after which the specified queue will be cleared.
        """

        # AtQueueMember timestamp fields are always naive, but the timestamp
        # from util.utc_to_system_time might not be.
        dt = util.utc_to_system_time(dt).replace(tzinfo=None)
        for mem in AtQueueMember.from_queue(queue):
            if mem.dt >= dt:
                subprocess.call(["atrm", str(mem.id)])

    @classmethod
    def clear_queue(cls, queue: str):
        cls.clear_queue_from(queue, datetime.fromtimestamp(0))

    @classmethod
    def add_switch_command(
        cls, prog_config: config.ProgramConfig, action: str, dt: datetime
    ):
        """
        Generate a new switch command and add it to the 'at' daemon queue.

        @param prog_config Current program configuration.
        @param action Switching action to schedule. Has to be either 'ON' or
        'FR'.
        @oaram dt Datetime on which to do the switching command.
        """

        cls.schedule_member(
            prog_config.gen_switch_command(action),
            dt,
            prog_config["environment"]["switch_queue"],
        )

    @staticmethod
    def remove_member(member: AtQueueMember):
        """
        Remove a queued job from the 'at' daemon list that has the same id as
        the passed member.

        @param member The member whose id is used to remove from queue.
        """

        subprocess.call(["atrm", str(member.id)])

    @classmethod
    def schedule_member(cls, command: str, dt: datetime, queue: str):
        """
        Schedule a new 'at' daemon job with command at specified time in the
        specified queue.

        @param command Command to schedule.
        @param dt Time to schedule command at.
        @param queue Queue to schedule command in.
        """

        wrapped_cmd = f'echo "{command}" | at -q {queue} -t {cls.datetime_to_at(dt)}'
        subprocess.call(
            wrapped_cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


class CronWrapper:
    """
    Namespacing class for encapsulating interaction with the crontab daemon,
    """

    @staticmethod
    def clear_fetch_cronjob(comment=FETCH_CRON_COMMENT):
        """
        Remove existing fetch cronjob.
        """

        with crontab.CronTab(user=True) as cron:
            cron.remove_all(comment=comment)

    @staticmethod
    def add_fetch_cronjob(
        prog_config: config.ProgramConfig, comment=FETCH_CRON_COMMENT
    ):
        """
        Add the fetch script to the cron daemon at 21:30 UTC.

        21:30 is chosen as it is far enough in the day where we realistically
        don't have to worry about the next days prices being posted yet.
        However, it is also early enough that timezone changes won't push the
        command into the next day.

        @param prog_config The global program configuration that is passed to
        the fetch script.
        """

        with crontab.CronTab(user=True) as cron:
            fetch_job = cron.new(
                command=prog_config.gen_fetch_command(), comment=comment
            )

            # Run at 21:30 every day
            sys_21_30 = util.get_21_30_market_as_sys()
            fetch_job.setall(f"{sys_21_30.minute} {sys_21_30.hour} * * *")


def script_pidfile(filepath=None) -> pid.PidFile:
    """
    Create a pidfile lock for 'at' queue access.

    @return Pidfile handle.
    """

    if filepath is None:
        uid = subprocess.check_output(["id", "-u"]).decode("UTF-8").strip()
        return pid.PidFile(f"/var/run/user/{uid}/{PIDFILE_NAME}.lock")
    else:
        return pid.PidFile(filepath)
