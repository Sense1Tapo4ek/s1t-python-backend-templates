from admin.metrics.adapters.driven.samplers import ProcessRssSampler


class TestProcessRssSampler:
    def test_current_rss_bytes_is_positive(self) -> None:
        sampler = ProcessRssSampler()
        rss = sampler.current_rss_bytes()
        assert rss > 0
