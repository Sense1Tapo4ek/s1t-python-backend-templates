from dishka import AsyncContainer, make_async_container

from admin.log.provider import AdminLogWebProvider
from admin.metrics.provider import AdminMetricsProvider
from admin.provider import AdminProvider
from auth.provider import AuthPortBindings, AuthProvider
from db_example.provider import (
    DbExampleInfraProvider,
    PerRequestDbExampleProvider,
    PooledDbExampleProvider,
)
from db_example_alchemy.provider import DbExampleAlchemyProvider
from shared.provider import SharedProvider


def build_container() -> AsyncContainer:
    return make_async_container(
        SharedProvider(),
        AdminProvider(),
        AdminLogWebProvider(),
        AdminMetricsProvider(),
        AuthProvider(),
        AuthPortBindings(),
        DbExampleInfraProvider(),
        PooledDbExampleProvider(),
        PerRequestDbExampleProvider(),
        DbExampleAlchemyProvider(),
    )
