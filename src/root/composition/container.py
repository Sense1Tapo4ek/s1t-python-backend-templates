from dishka import AsyncContainer, make_async_container

from admin.log.provider import AdminLogWebProvider
from admin.provider import AdminProvider
from auth.provider import AuthProvider
from db_example_litestar.provider import DbExampleLitestarProvider
from db_example_sddd.provider import (
    DbExampleSdddInfraProvider,
    PerRequestDbExampleSdddProvider,
    PooledDbExampleSdddProvider,
)
from metrics.provider import MetricsProvider
from shared.provider import SharedProvider


def build_container() -> AsyncContainer:
    return make_async_container(
        SharedProvider(),
        AdminProvider(),
        AdminLogWebProvider(),
        MetricsProvider(),
        AuthProvider(),
        DbExampleSdddInfraProvider(),
        PooledDbExampleSdddProvider(),
        PerRequestDbExampleSdddProvider(),
        DbExampleLitestarProvider(),
    )
