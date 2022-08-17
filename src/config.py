"""
Common program configuation logic.

This module is used both in the fetch script, as well as the on/off scripts.

Classes:
    ProgramConfig
"""

import os
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
    def check_config_keys(cls, req_subtree, config_subtree):
        """
        Make sure that a loaded configuration contains all the required config
        items.
        """
        if isinstance(req_subtree, list):
            for key in req_subtree:
                if key not in config_subtree.keys():
                    return False
        elif isinstance(req_subtree, dict):
            for (key, subtree) in req_subtree.items():
                if key not in config_subtree.keys()\
                    or not cls.check_config_keys(subtree, config_subtree[key]):
                    return False
        return True

    @classmethod
    def check_config_region(cls, region_code):
        return region_code.upper() in ACCEPTABLE_REGION_NAMES

    @classmethod
    def check_config(cls, unchecked):
        if not cls.check_config_keys(CONFIG_REQ_KEYS, unchecked):
            return (False, "Configuration file is missing required keys!")

        if not cls.check_config_region(unchecked['fetch']['region_code']):
            return (False, "Configuration region is not one of the available ones!")

        return (True, None)

    @classmethod
    def from_file(cls, filepath):
        """
        Load a configuration from a file and check it using check_config_keys.
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

    def get_heating_minutes(self, date):
        """
        Get configured heating minutes for the weekday of the passed datetime.
        """
        return list(self["heating-schedule"].values())[date.weekday()]

    def gen_fetch_command(self):
        return "{} {}/fetch.py -c {}".format(
            self['environment']['python'],
            os.getcwd(),
            self.source_file)

    def gen_switch_command(self, action):
        return "{} {}/switch.py -c {} -a {}".format(
            self['environment']['python'],
            os.getcwd(),
            self.source_file,
            action)
