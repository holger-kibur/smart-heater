import subprocess
import os
import io
from datetime import datetime
import pid
import crontab

from src import util

FETCH_CRON_COMMENT = 'smart-heater-fetch'

class AtQueueMember():
    def __init__(self, queue_member_str):
        fields = queue_member_str.split()
        self.id = int(fields[0])
        self.dt = datetime.strptime(
            " ".join(fields[1:6]),
            "%a %b %-d %H:%M:%S %Y")
        self.queue = fields[6]

def clear_fetch_cronjob():
    with crontab.CronTab(user=True) as cron:
        cron.remove_all(comment=FETCH_CRON_COMMENT)

def add_fetch_cronjob(prog_config):
    with crontab.CronTab(user=True) as cron:
        fetch_job = cron.new(
                command=prog_config.gen_fetch_command(),
                comment=FETCH_CRON_COMMENT)
        # Run at 23:30 every day
        fetch_job.setall('30 23 * * *')

def queue_pidfile():
    uid = subprocess.check_output(['id', '-u'])
    return pid.PidFile(f"/var/run/user/{uid}/smart-heater.lock")

def datetime_to_at(time: datetime) -> str:
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

def get_at_queue_members():
    at_queue = io.BytesIO(subprocess.check_output(['at', 'l']))
    queue_list = []
    for member_line in at_queue:
        queue_list.append(AtQueueMember(member_line.decode('UTF-8')))
    return sorted(queue_list, key=lambda x: x.dt)

def queue_filter(member_list, queue):
    for member in member_list:
        if member.queue == queue:
            yield member

def remove_member(member):
    subprocess.call(['atrm', member.id])

def schedule_member(command, dt, queue):
    wrapped_cmd = f"echo \"{command}\" | at -q {queue} -t {datetime_to_at(dt)}"
    subprocess.call(wrapped_cmd, shell=True)

def collect_queue(queue):
    members = []
    for sched in queue_filter(get_at_queue_members(), queue):
        remove_member(sched)
        members.append(sched)
    return sorted(members, key=lambda x: x.dt)

def clear_queue_from(queue, dt):
    members = get_at_queue_members()
    for mem in queue_filter(members, queue):
        if mem.dt >= dt:
            subprocess.call(['atrm', str(mem.id)])
