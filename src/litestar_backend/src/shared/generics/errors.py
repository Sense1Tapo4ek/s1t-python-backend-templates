class LayerError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class DomainError(LayerError):
    pass


class AppError(LayerError):
    pass


class NotFoundError(AppError):
    """An AppError signalling a missing resource; the driving adapter maps it to HTTP 404."""


class PortError(LayerError):
    pass
