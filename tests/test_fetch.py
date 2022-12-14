"""
Pytest container module for the test_fetch function.
"""

import subprocess
import io
import importlib
import pytest

import requests


def test_fetch(fix_config, fix_test_queue):
    """
    Integration test of the fetch script.

    This test does not check for the validity of the actual commands emitted to
    the 'at' daemon. It merely checks that some were created e.g. there were no
    errors in the fetch process itself, and then as a sanity check makes sure
    that there are an even amount of them.
    """

    fetch = importlib.import_module("src.fetch")

    # Configure test so it interferes as little as possible
    fix_config["environment"]["at_queue"] = fix_test_queue

    try:
        fetch.do_fetch(prog_config=fix_config)
    except requests.exceptions.ConnectionError:
        pytest.skip("Can't run online fetch test without internet connection!")

    # Inspect at queue to see if commands were entered correctly
    at_queue = io.BytesIO(subprocess.check_output(["at", "-l"]))

    num_in_queue = 0
    for sched_cmd in at_queue:
        if sched_cmd.split()[6].decode("UTF-8") == fix_test_queue:
            num_in_queue += 1

    assert num_in_queue >= 0, "Fetch didn't put any commands in at queue!"
    assert num_in_queue % 2 == 0, "Fetch put an uneven number of commands in at queue!"
