from dishka import AsyncContainer, make_async_container
from litestar.channels import ChannelsPlugin

from admin import AdminProvider
from admin.log import AdminLogWebProvider
from auth import AuthProvider
from db_example_litestar import DbExampleLitestarProvider
from media_example import MediaInfraProvider, MediaWebProvider
from shared.provider import SharedProvider


def build_container(*, channels: ChannelsPlugin) -> AsyncContainer:
    return make_async_container(
        SharedProvider(),
        AdminProvider(),
        AdminLogWebProvider(),
        AuthProvider(),
        DbExampleLitestarProvider(),
        MediaInfraProvider(),
        MediaWebProvider(),
        context={ChannelsPlugin: channels},
    )
