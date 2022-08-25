import sys
import os
import subprocess
import pytest

from src import config

TEST_CONF_CONFNAME = "/tmp/smart-heater-test-conf.toml"


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
            "switch_queue": "s",
            "script_dir": "DUMY_PATH",
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


def test_setup(setup_newconf_input, setup_newconf_conf):
    setup_inst = subprocess.Popen(
        [sys.executable, f"{os.getcwd()}/setup.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="UTF-8",
    )

    _, error = setup_inst.communicate(setup_newconf_input)
    assert not error

    assert os.path.exists(TEST_CONF_CONFNAME)

    loaded_conf = config.ProgramConfig.from_file(TEST_CONF_CONFNAME)
    os.remove(TEST_CONF_CONFNAME)

    assert setup_newconf_conf == loaded_conf
