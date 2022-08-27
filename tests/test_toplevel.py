import sys
import os
import subprocess
import pytest
import crontab

from src import config, manage, util

TEST_CONF_CONFNAME = "/tmp/smart-heater-test-conf.toml"
TEST_CRONJOB_COMMENT = "SMART_HEATER_TEST_JOB"
TEST_PIDFILE_NAME = "SMART_HEATER_TEST"


@pytest.fixture
def setup_newconf_input() -> str:
    return "\n".join(
        [
            "1",  # Language choice
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",  # Minutes per weekday
            "ee",  # Region code
            "1",  # GPIO pin number
            "n",  # Polarity choice
            TEST_CONF_CONFNAME,  # Confiuration name/path
        ]
    )


@pytest.fixture
def setup_newconf_conf() -> config.ProgramConfig:
    config_tree = {
        "heating-schedule": {
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
            "sunday": 7,
        },
        "fetch": {
            "url": "https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR",
            "region_code": "EE",
        },
        "environment": {
            "python": "DUMMY_EXEC",
            "switch_queue": "T",
            "script_dir": "DUMMY_PATH",
        },
        "hardware": {
            "switch_pin": 1,
            "reverse_polarity": False,
        },
        "logging": {
            "fetch_logfile": "TEST_FETCH_LOG.log",
            "switch_logfile": "TEST_SWITCH_LOG.log",
        },
    }
    check_result = config.ProgramConfig.check_config(config_tree)
    if not check_result[0]:
        pytest.fail(str(check_result[1]))
    return config.ProgramConfig(config_tree, "TEST_CONFIG")


def test_toplevel(setup_newconf_input, setup_newconf_conf):
    setup_inst = subprocess.Popen(
        [
            sys.executable,
            f"{os.getcwd()}/setup.py",
            "--_test_comment",
            TEST_CRONJOB_COMMENT,
            "--_test_pidfile",
            TEST_PIDFILE_NAME,
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="UTF-8",
    )
    _, error = setup_inst.communicate(setup_newconf_input)
    assert not error

    # Validate changes to filesystem
    assert os.path.exists(TEST_CONF_CONFNAME)
    loaded_conf = config.ProgramConfig.from_file(TEST_CONF_CONFNAME)
    assert setup_newconf_conf == loaded_conf

    # Validate changes to 'crontab' daemon.
    with crontab.CronTab(user=True) as cron:
        fetch_cronjobs = list(cron.find_comment(TEST_CRONJOB_COMMENT))
        assert len(fetch_cronjobs) == 1
        fetch_job = fetch_cronjobs[0]
        sys_21_30 = util.get_21_30_market_as_sys()
        assert fetch_job.minute == sys_21_30.minute
        assert fetch_job.hour == sys_21_30.hour

    # Run crontab fetch command
    fetch_inst = subprocess.Popen(
        [fetch_job.command, "--_test_pidfile", TEST_PIDFILE_NAME],
        stderr=subprocess.PIPE,
        text=True,
        encoding="UTF-8",
    )
    _, error = fetch_inst.communicate()
    assert not error
