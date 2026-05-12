from shared.generics.errors import DomainError


class MetricsError(DomainError):
    """Base for admin/metrics domain errors."""


class UnknownModuleError(MetricsError):
    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"unknown metrics module: {slug!r}")


class DuplicateSlugError(MetricsError):
    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"duplicate metrics module slug: {slug!r}")
