from litestar import Litestar

from root.composition.app import build_app


def create_app() -> Litestar:
    """Entry-point seam invoked by the ASGI server, the CLI, and tests.

    The actual app assembly lives in `root.composition.app.build_app`; this
    module is only the stable import path the runtime references.
    """
    return build_app()
