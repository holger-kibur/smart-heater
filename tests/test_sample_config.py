"""
Pytest container module for the test_sample_config function.
"""
import os

from src import config


def test_sample_config():
    """
    Test for whether the provided sample configuration actually contains all
    the keys that the program requires.
    """
    config.ProgramConfig.from_file(f"{os.getcwd()}/sample_conf.toml")
