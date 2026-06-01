from dishka import AsyncContainer, make_async_container

from admin.log.provider import AdminLogWebProvider
from admin.metrics.provider import AdminMetricsProvider
from admin.provider import AdminProvider
from auth.provider import AuthPortBindings, AuthProvider
from db_example_litestar.provider import DbExampleLitestarProvider
from db_example_sddd.provider import (
    DbExampleSdddInfraProvider,
    PerRequestDbExampleSdddProvider,
    PooledDbExampleSdddProvider,
)
from shared.provider import SharedProvider


def build_container() -> AsyncContainer:
    return make_async_container(
        SharedProvider(),
        AdminProvider(),
        AdminLogWebProvider(),
        AdminMetricsProvider(),
        AuthProvider(),
        AuthPortBindings(),
        DbExampleSdddInfraProvider(),
        PooledDbExampleSdddProvider(),
        PerRequestDbExampleSdddProvider(),
        DbExampleLitestarProvider(),
    )
