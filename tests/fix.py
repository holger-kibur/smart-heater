"""
Seperate module for pytest fixtures used in the other tests.
"""

import importlib
import pytest
from typing import Generator

from src import log, manage


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
def fix_test_queue() -> Generator[str, None, None]:
    TEST_QUEUE = "T"
    # Preliminary check to make sure the queue is empty
    if len(manage.AtQueueMember.from_queue(TEST_QUEUE)) > 0:
        pytest.fail("Test queue 'T' is already in use!")
    yield TEST_QUEUE
    # Clear queue from all the things we might have put into it
    manage.AtWrapper.clear_queue(TEST_QUEUE)
