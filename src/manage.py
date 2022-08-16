import subprocess
import io
from datetime import datetime
import pid

from src import util

class AtQueueMember():
    def __init__(self, queue_member_str):
        fields = queue_member_str.split()
        self.id = int(fields[0])
        self.dt = datetime.strptime(
            " ".join(fields[1:6]),
            "%a %b %-d %H:%M:%S %Y")
        self.queue = fields[6]

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
    return queue_list

def queue_filter(member_list, queue):
    for member in member_list:
        if member.queue == queue:
            yield member

def remove_member(member):
    subprocess.call(['atrm', member.id])

def schedule_member(command, dt, queue):
    wrapped_cmd = f"echo \"{command}\" | at -q {queue} -t {datetime_to_at(dt)}"
    subprocess.call(wrapped_cmd, shell=True)

def collect_queue():
    # TODO: Write this
    pass

def clear_queue_from(queue, dt):
    members = get_at_queue_members()
    for mem in queue_filter(members, queue):
        if mem.dt >= dt:
            subprocess.call(['atrm', str(mem.id)])
