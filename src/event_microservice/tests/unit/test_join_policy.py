from media_processing.domain import JoinPolicy


class TestJoinPolicy:
    def test_incomplete_below_fan_out(self) -> None:
        """Given fewer done jobs than fan_out, When checked, Then not complete."""
        assert JoinPolicy.is_complete(done_count=2, fan_out=3) is False

    def test_complete_at_fan_out(self) -> None:
        """Given done == fan_out, When checked, Then complete."""
        assert JoinPolicy.is_complete(done_count=3, fan_out=3) is True

    def test_complete_above_fan_out(self) -> None:
        """Given more done than fan_out (redelivery), When checked, Then complete."""
        assert JoinPolicy.is_complete(done_count=4, fan_out=3) is True
