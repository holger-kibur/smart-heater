"""
Functionality for verifying support of the underlying system.

Functions:
    verify_environment
"""

from importlib import import_module
import os
import shutil


def verify_environment(): 
    """
    Verify that the system the script is running on is supported.

    Returns: ([if this environment is supported], [verbose reason in case it isn't])
    """

    # Verify OS as linux-based
    if os.uname()[0].lower() != "linux":
        return (False, "Operating system needs to be linux-based!")

    # Verify that it's a raspberry pi
    try:
        with open("/sys/firmware/devicetree/base/model", "r", encoding="utf-8") as model_file:
            if "raspberry pi" not in model_file.read().lower():
                return (False, "Needs to be running on a Raspberry PI!")
    except FileNotFoundError:
        return (False, "Needs to be running on a Raspberry PI!")

    # Verfiy that GPIO is installed
    try:
        import_module("RPi.GPIO")
    except ModuleNotFoundError:
        return (False, "Couldn't import GPIO module!")

    # Verify that the crontab command exists
    if shutil.which("at") is None:
        return (False, "Environment needs to have the at command!")

    return (True, "")
