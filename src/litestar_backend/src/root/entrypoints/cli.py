import argparse

from root.config import RootConfig
from root.helpers.server import start_foreground, start_nohup, stop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="start_litestar",
        description="Litestar base project launcher",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--nohup",
        action="store_true",
        help="Start in background and tail the log",
    )
    mode.add_argument(
        "--stop",
        action="store_true",
        help="Stop the background server",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = RootConfig()
    if args.stop:
        stop(config)
    elif args.nohup:
        start_nohup(config)
    else:
        start_foreground(config)


if __name__ == "__main__":
    main()
