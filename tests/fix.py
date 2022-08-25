"""
Seperate module for pytest fixtures used in the other tests.
"""

import string
import subprocess
import io
import importlib
import pytest

from src import log


@pytest.fixture
def fix_logging():
    """
    Test fixture to configure the LoggerFactory class to test mode. This can be
    added to tests to remove the logger configuration boilerplate.
    """

    log.LoggerFactory.configure_test_logger()


@pytest.fixture
def fix_config(fix_logging):  # pylint: disable=redefined-outer-name,unused-argument
    """
    Test fixture to provide tests with a complete program configuration that
    can then be updated in the test itself.
    """

    config = importlib.import_module("src.config")
    config_tree = {
        "heating-schedule": {
            "monday": 60,
            "tuesday": 60,
            "wednesday": 60,
            "thursday": 60,
            "friday": 60,
            "saturday": 60,
            "sunday": 60,
        },
        "fetch": {
            "url": "https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR",
            "region_code": "EE",
        },
        "environment": {
            "python": "DUMMY_EXEC",
            "switch_queue": "a",
            "script_dir": "DUMMY PATH",
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
        pytest.fail(check_result[1])
    return config.ProgramConfig(config_tree, "TEST_CONFIG")


@pytest.fixture
def fix_empty_at_queue():
    """
    Test fixture that provides tests with an empty 'at' command queue. This
    function also cleans up commmands added to that queue after test
    completion.
    """

    at_list = io.BytesIO(subprocess.check_output(["at", "-l"]))
    queues = {k: False for k in list(string.ascii_letters)}
    used_queue = None
    for line in at_list:
        queues[line.split()[6].decode("UTF-8")] = True
    for queue, in_use in queues.items():
        if not in_use:
            used_queue = queue
            break
    else:
        pytest.fail("No empty at queues to use for tests!")

    yield used_queue

    # Cleanup all commands in used queue
    at_list_after = io.BytesIO(subprocess.check_output(["at", "-l"]))
    for line in at_list_after:
        if line.split()[6].decode("UTF-8") == used_queue:
            subprocess.call(["atrm", line.split()[0].decode("UTF-8")])
