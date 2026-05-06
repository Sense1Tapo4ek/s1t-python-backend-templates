from dishka import AsyncContainer, make_async_container
from litestar.channels import ChannelsPlugin

from admin.log.provider import AdminLogPortBindings, AdminLogProvider
from admin.provider import AdminProvider
from auth.provider import AuthPortBindings, AuthProvider
from shared.provider import SharedProvider


def build_container(*, channels_plugin: ChannelsPlugin) -> AsyncContainer:
    """`channels_plugin` must be the same instance passed to
    `Litestar(plugins=[...])` — publishers and subscribers share one backend.
    """
    return make_async_container(
        SharedProvider(channels_plugin=channels_plugin),
        AdminProvider(),
        AdminLogProvider(),
        AdminLogPortBindings(),
        AuthProvider(),
        AuthPortBindings(),
    )
