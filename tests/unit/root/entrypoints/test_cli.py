import pytest

from root.entrypoints.cli import build_parser


def test_parser_defaults_to_foreground_start() -> None:
    args = build_parser().parse_args([])

    assert args.nohup is False
    assert args.stop is False


def test_parser_accepts_nohup_mode() -> None:
    args = build_parser().parse_args(["--nohup"])

    assert args.nohup is True
    assert args.stop is False


def test_parser_accepts_stop_mode() -> None:
    args = build_parser().parse_args(["--stop"])

    assert args.nohup is False
    assert args.stop is True


def test_parser_rejects_conflicting_modes() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--nohup", "--stop"])
