class LayerError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class DomainError(LayerError):
    pass


class AppError(LayerError):
    pass


class PortError(LayerError):
    pass


class AdapterError(LayerError):
    pass
