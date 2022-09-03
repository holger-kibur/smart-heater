"""
Script that configures and executes the program price fetch, scheduling, and
uploading logic.

This is meant to be ran from the command line.
"""

import argparse
import toml

from src import log, util, config, manage, fetch


def main(args):
    # TODO: Rethink environment check
    # Get program configuration
    prog_config = config.ProgramConfig.from_file(args.configfile[0])
    if prog_config is None:
        # Couldn't find configuration file
        util.exit_critical_bare("Couldn't find configuration file!")

    # Configure logger factory
    log.LoggerFactory.configure_logger(
        args.verbose, prog_config["logging"]["fetch_logfile"], args.debug
    )

    # Execute main fetch logic
    if args._test_datafile:
        try:
            pricedata = toml.load(args._test_datafile[0])
        except FileNotFoundError:
            util.exit_critical_bare("Couldn't find test price data!")
        fetch.do_fetch(prog_config, test_pricedata=pricedata)
    else:
        fetch.do_fetch(prog_config)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print log messages to stdout as well.",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Log debug messages."
    )
    parser.add_argument(
        "-s",
        "--skipenvcheck",
        action="store_true",
        help="Don't proactively check for required execution environment.",
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
    parser.add_argument(
        "--_test_datafile",
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
