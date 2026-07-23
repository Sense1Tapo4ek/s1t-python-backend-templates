class LayerError(Exception):
    pass


class DomainError(LayerError):
    pass


class AppError(LayerError):
    pass


class PortError(LayerError):
    pass
