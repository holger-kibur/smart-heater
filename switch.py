"""
Command line entry point for switching program.
"""

import argparse
import importlib
from typing import Optional

from src import log, verify_env, util, config, manage


def do_switch(config, action):
    GPIO = importlib.import_module("RPi.GPIO")
    out_pin = config["hardware"]["switch_pin"]
    pin_state = GPIO.HIGH if action == "ON" else GPIO.LOW
    if config["hardware"]["reverse_polarity"]:
        # Reverse the pin state
        pin_state = GPIO.LOW if pin_state == GPIO.HIGH else GPIO.HIGH
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(0)
    GPIO.setup(out_pin, GPIO.OUT)
    GPIO.output(out_pin, pin_state)


def main(args):
    prog_config = config.ProgramConfig.from_file(args.configfile[0])
    if prog_config is None:
        # Couldn't find configuration file
        util.exit_critical_bare("Couldn't find configuration file!")

    log.LoggerFactory.configure_logger(
        verbose=False, logfile=prog_config["logging"]["switch_logfile"], debug=False
    )

    if not args._test_dryrun:
        do_switch(prog_config, args.action[0])

    log.LoggerFactory.get_logger("SWITCH").info(
        f"{'DRYRUN!' if args._test_dryrun else ''}Heating switched {args.action[0]}!"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--action",
        nargs=1,
        required=True,
        choices=["ON", "OFF"],
        help="Switching action to perform.",
    )
    parser.add_argument(
        "-c",
        "--configfile",
        nargs=1,
        required=True,
        help="Required configuration file path.",
    )
    parser.add_argument(
        "--_test_pidfile",
        nargs=1,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--_test_dryrun", action="store_true", help=argparse.SUPPRESS)
    parsed_args = parser.parse_args()

    if parsed_args._test_pidfile:
        pid_handle = manage.script_pidfile(parsed_args._test_pidfile[0])
    else:
        pid_handle = manage.script_pidfile()
    with pid_handle:
        main(parsed_args)
