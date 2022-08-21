"""
Common program configuation logic.

This module is used both in the fetch script, as well as the on/off scripts.

Classes:
    ProgramConfig
"""
from __future__ import annotations

from datetime import datetime
import os
from typing import Union, Optional
import toml

from . import util

ACCEPTABLE_REGION_NAMES = [
    'SYS', 'SE1', 'SE2', 'SE3', 'SE4', 'FI', 'DK1', 'DK2', 'OSLO', 'KR.SAND',
    'BERGEN', 'MOLDE', 'TR.HEIM', 'TROMSE', 'EE', 'LV', 'LT', 'AT', 'BE',
    'DE-LU', 'FR', 'NL',
]

WEEKDAY_KEYS = [
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
]

CONFIG_REQ_KEYS = {
    'heating-schedule': WEEKDAY_KEYS,
    'fetch': [
        'url',
        'region_code',
    ],
    'environment': [
        'python',
        'switch_queue',
    ],
    'hardware': [
        'switch_pin',
        'reverse_polarity',
    ],
    'logging': [
        'fetch_logfile',
        'switch_logfile',
    ],
}


class ProgramConfig():
    """
    Convenient access to a full program configuration.

    Configuration keys can be accessed by indexing the instance like a dict.
    Instance also provudes utility functions for non-trivial configuration
    information.

    Configuration file doesn't necessarily need to have all fields assigned. All
    non-provided fields revert to their hardcoded defaults.
    """

    @classmethod
    def check_config_keys(
            cls,
            req_subtree: Union[dict, list],
            config_subtree: dict) -> tuple[bool, Optional[str]]:
        """
        Recursive function to ensure that a parsed configuration file contains
        all the required keys.

        In case it doesn't this function will indicate which key is missing.

        @param req_subtree Toplevel call should pass CONFIG_REQ_KEYS. @param
        config_subtree Toplevel call should pass the parsed configuration file
        dictionary.

        @return If the configration is valid, return (True, None). Otherwise,
        return (False, #MISSING KEY#),
        """

        if isinstance(req_subtree, list):
            for key in req_subtree:
                if key not in config_subtree.keys():
                    return (False, key)
        elif isinstance(req_subtree, dict):
            for (key, subtree) in req_subtree.items():
                if key in config_subtree.keys():
                    downtree = cls.check_config_keys(
                        subtree, config_subtree[key])
                    if not downtree[0]:
                        return downtree
                else:
                    return (False, key)
        return (True, None)

    @classmethod
    def check_config_region(cls, region_code: str) -> bool:
        """
        Check whether the passed string is an acceptable Nordpool region code.

        @param region_code The possible region code

        @return True == The region code is valid, otherwise False.
        """

        return region_code.upper() in ACCEPTABLE_REGION_NAMES

    @classmethod
    def check_config(cls, unchecked: dict) -> tuple[bool, Optional[str]]:
        """
        Check whether the passed dictionary is a valid smart-heater program
        configuration.

        @param unchecked The unvalidated configuation dictionary. Most likely
        this comes from toml.load().

        @return If configuration is valid, return (True, None). Otherwise,
        return (False, #REASON#)
        """

        key_check_res = cls.check_config_keys(CONFIG_REQ_KEYS, unchecked)
        if not key_check_res[0]:
            return (False, f"Configuration file is missing required key: {key_check_res[1]}!")

        if not cls.check_config_region(unchecked['fetch']['region_code']):
            return (False, "Configuration region is not one of the available ones!")

        return (True, None)

    @classmethod
    def from_file(cls, filepath: str) -> ProgramConfig:
        """
        Load a configuration file from a filepath, validate it, and use it to
        construct a new ProgramConfig.

        @param filepath The path to the configuration file.

        @return The new ProgramConfig instance.
        """

        try:
            from_file: dict = toml.load(filepath)
        except FileNotFoundError:
            util.exit_critical_bare("Couldm't find configuration file!")

        check_res = cls.check_config(from_file)
        if not check_res[0]:
            util.exit_critical_bare(check_res[1])

        return cls(from_file, filepath)

    def __init__(self, config_tree, source_file):
        self.config_tree = config_tree
        self.source_file = source_file

    def __getitem__(self, items):
        return self.config_tree.__getitem__(items)

    def __setitem__(self, key, val):
        self.config_tree[key] = val

    def get_heating_minutes(self, date: datetime) -> int:
        """
        Get configured heating minutes for the weekday of the passed datetime.

        @param date A time within the query weekday.

        @return Number of heating minutes.
        """

        return list(self["heating-schedule"].values())[date.weekday()]

    def gen_fetch_command(self) -> str:
        """
        Generate a command that will execute the fetch script using the current
        instance configuration.

        @return The command string.
        """

        return "{} {}/fetch.py -c {}".format(
            self['environment']['python'],
            os.getcwd(),
            self.source_file)

    def gen_switch_command(self, action) -> str:
        """
        Generate a command that will execute the switch script using the
        current instance configuration.

        @param action Specify the switching action. Either 'ON' or 'OFF'.

        @return The command string.
        """

        return "{} {}/switch.py -c {} -a {}".format(
            self['environment']['python'],
            os.getcwd(),
            self.source_file,
            action)
