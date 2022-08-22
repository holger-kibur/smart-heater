"""
Module to encapsulate all the program's interaction with operating system daemons.

The daemons used are 'at' and 'crontab'.
"""
from __future__ import annotations

from collections.abc import Generator
import subprocess
import io
from datetime import datetime
import pid
import crontab

from src import util, config

FETCH_CRON_COMMENT = 'smart-heater-fetch'


class AtQueueMember():
    """
    Utility class for representing scheduled jobs in the 'at' daemon queue.
    This class only parses and stores fields necessary for program function.
    """

    def __init__(self, queue_member_str):
        fields = queue_member_str.split()
        self.id = int(fields[0])
        self.dt = util.system_time_to_utc(
                datetime.strptime(
                    " ".join(fields[1:6]), "%a %b %d %H:%M:%S %Y"))
        self.queue = fields[6]


class AtWrapper():
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
            systime.year,
            systime.month,
            systime.day,
            systime.hour,
            systime.minute)

    @staticmethod
    def get_at_queue_members() -> list[AtQueueMember]:
        """
        Get all current members of the 'at' daemon queue.

        @return Unsorted and unfiltered list of all members.
        """

        at_queue = io.BytesIO(subprocess.check_output(['at', '-l']))
        queue_list = []
        for member_line in at_queue:
            queue_list.append(AtQueueMember(member_line.decode('UTF-8')))
        return queue_list

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
        members = cls.get_at_queue_members()
        for mem in cls.queue_filter(members, queue):
            if mem.dt >= dt:
                subprocess.call(['atrm', str(mem.id)])

    @classmethod
    def add_switch_command(cls, prog_config: config.ProgramConfig, action: str, dt: datetime):
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
            prog_config['environment']['switch_queue'])

    @staticmethod
    def queue_pidfile() -> pid.PidFile:
        """
        Create a pidfile lock for 'at' queue access.

        @return Pidfile handle.
        """

        uid = subprocess.check_output(['id', '-u']).decode('UTF-8').strip()
        return pid.PidFile(f"/var/run/user/{uid}/smart-heater.lock")

    @staticmethod
    def queue_filter(
            member_list: list[AtQueueMember],
            queue: str) -> Generator[AtQueueMember, None, None]:
        """
        Filter a list of 'at' daemmon members by queue.

        @param member_list List of 'at' daemon members.
        @param queue Character representing 'at' queue that should be retained.

        @return Generator of members in the specified queue.
        """

        for member in member_list:
            if member.queue == queue:
                yield member

    @staticmethod
    def remove_member(member: AtQueueMember):
        """
        Remove a queued job from the 'at' daemon list that has the same id as
        the passed member.

        @param member The member whose id is used to remove from queue.
        """

        subprocess.call(['atrm', str(member.id)])

    @classmethod
    def schedule_member(cls, command: str, dt: datetime, queue: str):
        """
        Schedule a new 'at' daemon job with command at specified time in the
        specified queue.

        @param command Command to schedule.
        @param dt Time to schedule command at.
        @param queue Queue to schedule command in.
        """

        wrapped_cmd = f"echo \"{command}\" | at -q {queue} -t {cls.datetime_to_at(dt)}"
        subprocess.call(wrapped_cmd, shell=True)


class CronWrapper():
    """
    Namespacing class for encapsulating interaction with the crontab daemon,
    """

    @staticmethod
    def clear_fetch_cronjob():
        """
        Remove existing fetch cronjob.
        """

        with crontab.CronTab(user=True) as cron:
            cron.remove_all(comment=FETCH_CRON_COMMENT)

    @staticmethod
    def add_fetch_cronjob(prog_config: config.ProgramConfig):
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
                command=prog_config.gen_fetch_command(),
                comment=FETCH_CRON_COMMENT)

            # Run at 21:30 every day
            utc_21_30 = util.market_time_to_utc(datetime(
                year=1970, month=1, day=1, hour=21, minute=30, second=0))
            sys_21_30 = util.utc_to_system_time(utc_21_30)
            fetch_job.setall(f'{sys_21_30.minute} {sys_21_30.hour} * * *')
