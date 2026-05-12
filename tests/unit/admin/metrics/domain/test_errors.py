from admin.metrics.domain import (
    DuplicateSlugError,
    MetricsError,
    UnknownModuleError,
)
from shared.generics.errors import DomainError


class TestErrorHierarchy:
    def test_unknown_module_is_metrics_error(self) -> None:
        assert issubclass(UnknownModuleError, MetricsError)
        assert issubclass(MetricsError, DomainError)

    def test_unknown_module_carries_slug(self) -> None:
        err = UnknownModuleError(slug="payments")
        assert err.slug == "payments"
        assert "payments" in str(err)

    def test_duplicate_slug_carries_slug(self) -> None:
        err = DuplicateSlugError(slug="http")
        assert err.slug == "http"
        assert "http" in str(err)
