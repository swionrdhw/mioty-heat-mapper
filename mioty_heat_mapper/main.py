import argparse
import logging
import sys

from pathlib import Path

from mioty_heat_mapper import __version__
from mioty_heat_mapper.state import init_config, load_config
from mioty_heat_mapper.graph import generate_graphs
from mioty_heat_mapper.gui import start_gui


def driver() -> None:
    """Handles the arguments for the package."""
    parser = argparse.ArgumentParser(
        description="Generates mioty network quality heat maps."
    )
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        help="Prints debug statements to a log file (debug.log).",
    )
    subparsers = parser.add_subparsers(dest="mode")

    init = subparsers.add_parser(
        "init",
        description="Creates a default configuration for a measurement run.",
        help="Creates a default configuration for a measurement run.",
        parents=[parent_parser],
    )
    init.add_argument(
        "--config",
        "-c",
        dest="config_path",
        required=False,
        default="config.json",
        help="Path to configuration file (default 'config.json').",
    )

    run = subparsers.add_parser(
        "run",
        description="Runs application to gather network quality measurements",
        help="Runs application to gather network quality measurements",
        parents=[parent_parser],
    )
    run.add_argument(
        "--config",
        "-c",
        dest="config_path",
        required=True,
        default="config.json",
        help="Path to configuration file (default 'config.json').",
    )

    plot = subparsers.add_parser(
        "plot",
        description="Generates plots from network quality measurements",
        help="Generates plots from network quality measurements",
        parents=[parent_parser],
    )
    plot.add_argument(
        "--config",
        "-c",
        dest="config_path",
        required=True,
        default="config.json",
        help="Path to configuration file (default 'config.json').",
    )

    subparsers.add_parser(
        "help",
        description="Shows this help message and exits.",
        help="Shows this help message and exits.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Shows the version number and exits.",
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit(1)

    if args.version:
        print(__version__)
        exit()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%y-%m-%d %H:%M:%S",
            filename="debug.log",
        )
        logging.debug("Enabled debug mode")

    config_path = Path(args.config_path)

    if args.mode == "init":
        init_config(config_path)
        parser.exit()

    elif args.mode == "help":
        parser.print_help()
        parser.exit()

    if not config_path.exists():
        parser.exit(1, f"Config file does not exist: {config_path}")

    config = load_config(config_path)

    config.validate_or_exit()

    if args.mode == "run":
        start_gui(config_path, config)

    elif args.mode == "plot":
        generate_graphs(config_path, config)


def __init__() -> None:
    driver()
