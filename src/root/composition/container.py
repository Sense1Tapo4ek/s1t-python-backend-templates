from dishka import AsyncContainer, make_async_container
from litestar import Litestar

from admin.log.provider import AdminLogWebProvider
from admin.provider import AdminProvider
from auth.provider import AuthProvider
from db_example_litestar.provider import DbExampleLitestarProvider
from metrics.provider import MetricsProvider
from orders.provider import OrdersInfraProvider, OrdersWebProvider
from shared.provider import SharedProvider


def build_container(app: Litestar) -> AsyncContainer:
    return make_async_container(
        SharedProvider(),
        AdminProvider(),
        AdminLogWebProvider(),
        MetricsProvider(),
        AuthProvider(),
        DbExampleLitestarProvider(),
        OrdersInfraProvider(),
        OrdersWebProvider(),
        context={Litestar: app},
    )
