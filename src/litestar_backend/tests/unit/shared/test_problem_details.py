from litestar.plugins.problem_details import ProblemDetailsException

from shared.adapters.problem_details import (
    _type_uri,
    adapter_to_problem,
    app_to_problem,
    domain_to_problem,
    not_found_to_problem,
    port_to_problem,
    unexpected_to_problem,
)
from shared.generics.errors import AdapterError, AppError, DomainError, PortError


class FakeAlreadyPaid(DomainError):
    pass


def test_type_uri_kebabs_classname() -> None:
    assert _type_uri(FakeAlreadyPaid("x")) == "urn:litestar-base:error:fake-already-paid"


def test_domain_converter_exposes_message() -> None:
    pd = domain_to_problem(FakeAlreadyPaid("order 1 already paid"))
    assert isinstance(pd, ProblemDetailsException)
    assert pd.status_code == 409
    assert pd.detail == "order 1 already paid"
    assert pd.type_ == "urn:litestar-base:error:fake-already-paid"


def test_app_converter_is_422() -> None:
    pd = app_to_problem(AppError("nope"))
    assert pd.status_code == 422
    assert pd.detail == "nope"


def test_not_found_converter_is_404() -> None:
    pd = not_found_to_problem(AppError("missing"))
    assert pd.status_code == 404


def test_port_converter_hides_internals() -> None:
    pd = port_to_problem(PortError("secret dsn timeout at 10.0.0.1"))
    assert pd.status_code == 503
    assert pd.detail == "Service temporarily unavailable"
    assert "secret" not in (pd.detail or "")


def test_adapter_converter_is_generic_500() -> None:
    pd = adapter_to_problem(AdapterError("boom"))
    assert pd.status_code == 500
    assert pd.detail == "Internal server error"


def test_unexpected_converter_is_generic_500() -> None:
    pd = unexpected_to_problem(Exception("x"))
    assert pd.status_code == 500
    assert pd.detail == "Internal server error"
