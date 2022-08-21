"""
Script that configures and executes the program price fetch, scheduling, and
uploading logic.

This is meant to be ran from the command line.
"""

import argparse

from src import log, util, verify_env, config

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print log messages to stdout as well.")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Log debug messages.")
    parser.add_argument("-s", "--skipenvcheck", action="store_true",
                        help="Don't proactively check for required execution environment.")
    parser.add_argument("-c", "--configfile", nargs=1, required=True,
                        help="Required configuration file path.")
    args = parser.parse_args()

    # Verify environment
    if not args.skipenvcheck:
        verify_result = verify_env.verify_environment()
        if not verify_result[0]:
            util.exit_critical_bare(
                f"Environment not suitable: {verify_result[1]}")

    # Get program configuration
    prog_config = config.ProgramConfig.from_file(args.configfile[0])
    if prog_config is None:
        # Couldn't find configuration file
        util.exit_critical_bare("Couldn't find configuration file!")

    # Configure logger factory
    log.LoggerFactory.configure_logger(args.verbose,
                                       prog_config['logging']['fetch_logfile'],
                                       args.debug)

    # Import rest of modules
    from src import fetch

    # Execute main fetch logic
    fetch.do_fetch(prog_config)
