from prometheus_client import REGISTRY

from db_example_sddd.ports.driven import MetricsAcl
from metrics.adapters.driven import PrometheusSink
from metrics.ports.driving import MetricsFacade


def test_acl_delegates_to_real_metrics_facade() -> None:
    """
    Given a MetricsAcl over a real MetricsFacade+PrometheusSink,
    When increment/observe are called through the ACL,
    Then the underlying prometheus series record the values (not just register).
    """
    facade = MetricsFacade(_sink=PrometheusSink())
    acl = MetricsAcl(_facade=facade)

    acl.increment("acl_roundtrip_counter_total")
    acl.observe("acl_roundtrip_seconds", 0.01)

    # Assert on recorded values, not mere cache membership: a no-op ACL would
    # still register the series but leave the counter at 0 / count at 0.
    assert REGISTRY.get_sample_value("acl_roundtrip_counter_total") == 1.0
    assert REGISTRY.get_sample_value("acl_roundtrip_seconds_count") == 1.0
