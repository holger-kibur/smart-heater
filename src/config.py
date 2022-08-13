"""
Common program configuation logic.

This module is used both in the fetch script, as well as the on/off scripts.

Classes:
    ProgramConfig
"""

import toml

from . import util

CONFIG_REQ_KEYS = {
    'heating-schedule': [
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
    ],
    'fetch': [
        'url',
        'country_code',
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
    def check_config(cls, req_subtree, config_subtree):
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
                    or not cls.check_config(subtree, config_subtree[key]):
                    return False
        return True

    @classmethod
    def from_file(cls, filepath):
        """
        Load a configuration from a file and check it using check_config.
        """
        try:
            from_file: dict = toml.load(filepath)
        except FileNotFoundError:
            util.exit_critical_bare("Couldm't find configuration file!")

        if not cls.check_config(CONFIG_REQ_KEYS, from_file):
            util.exit_critical_bare("Configuration file is missing required keys!")

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
