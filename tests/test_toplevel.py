from datetime import timedelta
import io
import shutil
import sys
import os
import subprocess
import pytest
import crontab
import toml
from typing import Generator

from src import config, util, manage

TEST_REGION = "EE"
DAYS_OF_THE_WEEK = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
TEST_DAYS = DAYS_OF_THE_WEEK[:-2]


@pytest.fixture
def fix_test_fpaths() -> Generator[dict, None, None]:
    filepaths = {
        "fetch_logfile": "/tmp/SMARTHEATER_TEST_FETCH.log",
        "switch_logfile": "/tmp/SMARTHEATER_TEST_SWITCH.log",
        "confpath": "/tmp/smart-heater-test-conf.toml",
        "pidfile": "/tmp/smart-heater-test.lock",
    }
    yield filepaths
    for fpath in filepaths.values():
        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass  # If the file doesn't exist, good!


@pytest.fixture
def fix_test_logdir() -> Generator[str, None, None]:
    TEST_LOGDIR = "/tmp/smart-heater-test-logs"
    os.mkdir(TEST_LOGDIR)
    yield TEST_LOGDIR
    shutil.rmtree(TEST_LOGDIR)


@pytest.fixture
def fix_test_jobcomment() -> Generator[str, None, None]:
    TEST_JOBCOMMENT = "SMART_HEATER_TEST_JOB"
    yield TEST_JOBCOMMENT
    manage.CronWrapper.clear_fetch_cronjob(comment=TEST_JOBCOMMENT)


def day_to_path(day):
    return os.getcwd() + "/tests/prices/" + day + ".toml"


def print_popen(inst):
    print("Executed: ", " ".join(list(inst.args)))


def conv_to_queue_members(
    event_list, queue
) -> Generator[manage.AtQueueMember, None, None]:
    for event in event_list:
        event_market_time = util.next_market_day_start() + timedelta(
            hours=int(event[1]), minutes=int(event[1] * 100) % 100
        )
        yield manage.AtQueueMember(
            0,  # Id doesn't matter in this case
            util.market_time_to_utc(event_market_time).replace(tzinfo=None),
            queue,
            manage.EventType.ON if event[0] == 0 else manage.EventType.OFF,
        )


def generate_setup_input(heating_schedule, confpath):
    input_str = ""

    # Language selection
    input_str += "english\n"

    # Heating schedule
    for day in DAYS_OF_THE_WEEK:
        input_str += str(heating_schedule[day]) + "\n"

    # Region code
    input_str += TEST_REGION + "\n"

    # GPIO pin number
    input_str += "1\n"

    # Polarity
    input_str += "n\n"

    # Configuration name
    input_str += confpath + "\n"

    return input_str


def test_toplevel(
    fix_test_fpaths, fix_test_queue, fix_test_jobcomment, fix_test_logdir
):
    # Global test parameters
    heating_schedule = {}
    expected_events = {}

    # Load test data files and parse parameters
    for test_day in TEST_DAYS:
        tree = toml.load(day_to_path(test_day))
        day = DAYS_OF_THE_WEEK[tree["weekday"]]
        heating_schedule[day] = tree["minutes"]
        expected_events[day] = list(
            conv_to_queue_members(tree["events"], fix_test_queue)
        )

    # Fill in missing days which don't have test cases
    for day in DAYS_OF_THE_WEEK:
        if day not in heating_schedule.keys():
            heating_schedule[day] = 0

    # Generate expected configuration
    expected_conf = {
        "heating-schedule": heating_schedule,
        "fetch": {
            "url": "https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR",
            "region_code": TEST_REGION,
        },
        "environment": {
            "python": sys.executable,
            "switch_queue": fix_test_queue,
            "script_dir": os.getcwd(),
        },
        "hardware": {
            "switch_pin": 1,
            "reverse_polarity": False,
        },
        "logging": {
            "fetch_logfile": fix_test_logdir + "/fetch.log",
            "switch_logfile": fix_test_logdir + "/switch.log",
        },
    }
    check_result = config.ProgramConfig.check_config(expected_conf)
    assert check_result[0], check_result[1]

    # Run setup script
    setup_inst = subprocess.Popen(
        [
            sys.executable,
            f"{os.getcwd()}/setup.py",
            "--logdir",
            fix_test_logdir,
            "--queue",
            fix_test_queue,
            "--_test_comment",
            fix_test_jobcomment,
            "--_test_pidfile",
            fix_test_fpaths["pidfile"],
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        encoding="UTF-8",
    )
    print_popen(setup_inst)
    _, error = setup_inst.communicate(
        generate_setup_input(heating_schedule, fix_test_fpaths["confpath"])
    )
    assert not error

    # Validate setup-generated configuration
    loaded_conf = config.ProgramConfig.from_file(fix_test_fpaths["confpath"])
    assert loaded_conf == config.ProgramConfig(expected_conf, "DUMMY_FILE")

    # Validate changes to 'crontab' daemon.
    with crontab.CronTab(user=True) as cron:
        fetch_cronjobs = list(cron.find_comment(fix_test_jobcomment))
        assert len(fetch_cronjobs) == 1
        fetch_job = fetch_cronjobs[0]
        sys_21_30 = util.get_21_30_market_as_sys()
        assert fetch_job.minute == sys_21_30.minute
        assert fetch_job.hour == sys_21_30.hour

    switch_commands = []

    # Launch fetch jobs with test configuration
    for test_day in TEST_DAYS:
        # Run crontab fetch command
        fetch_inst = subprocess.Popen(
            fetch_job.command.split(" ")
            + [
                "-v",
                "--_test_pidfile",
                fix_test_fpaths["pidfile"],
                "--_test_datafile",
                day_to_path(test_day),
            ],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            encoding="UTF-8",
        )
        print_popen(fetch_inst)
        _, error = fetch_inst.communicate()
        assert not error

        # Ensure correct output to test queue
        test_members = manage.AtQueueMember.from_queue(fix_test_queue)
        expected = expected_events[test_day]
        assert len(test_members) == len(expected)
        assert not any(
            [
                not test_members[i].is_equivalent(expected[i])
                for i in range(len(test_members))
            ]
        )

        # Save commands for later
        for member in test_members:
            longout = io.StringIO(
                subprocess.check_output(
                    ["at", "-c", str(member.id)], text=True, encoding="UTF-8"
                )
            )
            switch_commands.append(longout.readlines()[-2].strip())

        # Clear queue
        manage.AtWrapper.clear_queue(fix_test_queue)

    # Ensure that some logs were printed in the proper place by fetch.
    assert os.path.exists(fix_test_logdir + "/fetch.log")

    for switch_command in switch_commands:
        switch_inst = subprocess.Popen(
            switch_command.split(" ")
            + [
                "--_test_pidfile",
                fix_test_fpaths["pidfile"],
                "--_test_dryrun",
            ],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            encoding="UTF-8",
        )
        print_popen(switch_inst)
        _, error = switch_inst.communicate()
        assert not error

    # Ensure logs were printed in correct place by switch
    assert os.path.exists(fix_test_logdir + "/switch.log")
