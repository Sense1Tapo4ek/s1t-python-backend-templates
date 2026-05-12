import pytest

from admin.metrics.domain import WorkerIdVo


class TestWorkerIdVo:
    def test_format_is_host_colon_pid(self) -> None:
        wid = WorkerIdVo(host="host42", pid=12345)
        assert str(wid) == "host42:12345"

    def test_pid_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            WorkerIdVo(host="host42", pid=0)

    def test_host_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError):
            WorkerIdVo(host="", pid=12345)

    def test_parse_roundtrip(self) -> None:
        original = WorkerIdVo(host="host42", pid=12345)
        parsed = WorkerIdVo.parse(str(original))
        assert parsed == original

    def test_parse_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            WorkerIdVo.parse("no-colon-here")
