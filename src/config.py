"""
Common program configuation logic.

This module is used both in the fetch script, as well as the on/off scripts.

Classes:
    ProgramConfig
"""

import toml

from . import log

DEFAULT_CONFIG = {
    "heating-schedule": {
        "monday": 0,
        "tuesday": 0,
        "wednesday": 0,
        "thursday": 0,
        "friday": 0,
        "saturday": 0,
        "sunday": 0,
    },
    "fetch": {
        "url": None,
        "country_code": "EE",
    }
}

logger = log.LoggerFactory.get_logger("CONFIG")


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
    def from_default(cls):
        config = {}

        for key, val in DEFAULT_CONFIG.items():
            if isinstance(val, (dict, list)):
                config[key] = val.copy()
            else:
                config[key] = val

        return config

    @classmethod
    def from_file(cls, filepath):
        try:
            from_file: dict = toml.load(filepath)
        except FileNotFoundError:
            logger.error("Could't find configuration file!")
            return None

        config = cls.from_default()

        for key, val in config.items():
            if key in from_file.keys():
                file_val = from_file[key]
                if isinstance(val, dict) and isinstance(file_val, dict):
                    val.update(file_val)
                else:
                    config[key] = file_val

        return cls(config)

    def __init__(self, config_tree):
        self.config_tree = config_tree

    def __getitem__(self, items):
        return self.config_tree.__getitem__(items)

    def get_heating_minutes(self, date):
        return list(self["heating-schedule"].values())[date.weekday()]
