"""
Command line entry point for switching program.
"""

import argparse
import importlib

from src import log, verify_env, util, config, manage


def main(args):
    verify_result = verify_env.verify_environment()
    if not verify_result[0]:
        util.exit_critical_bare(f"Environment not suitable: {verify_result[1]}")

    # verify_environment ensures that we can import this, but to satisfy
    # static analysis on non-rpi environments, we have to do it this way.
    GPIO = importlib.import_module("RPi.GPIO")

    prog_config = config.ProgramConfig.from_file(args.configfile[0])
    if prog_config is None:
        # Couldn't find configuration file
        util.exit_critical_bare("Couldn't find configuration file!")

    log.LoggerFactory.configure_logger(
        verbose=False, logfile=prog_config["logging"]["switch_logfile"], debug=False
    )

    out_pin = prog_config["hardware"]["switch_pin"]
    pin_state = GPIO.HIGH if args.action[0] == "ON" else GPIO.LOW

    if prog_config["hardware"]["reverse_polarity"]:
        # Reverse the pin state
        pin_state = GPIO.LOW if pin_state == GPIO.HIGH else GPIO.HIGH

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(0)
    GPIO.setup(out_pin, GPIO.OUT)
    GPIO.output(out_pin, pin_state)

    log.LoggerFactory.get_logger("SWITCH").info(
        f"Heating switched {args.action[0]} (pin {pin_state})!"
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
    parsed_args = parser.parse_args()

    if parsed_args._test_pidfile:
        pid_handle = manage.script_pidfile(parsed_args._test_pidfile[0])
    else:
        pid_handle = manage.script_pidfile()
    with pid_handle:
        main(parsed_args)
