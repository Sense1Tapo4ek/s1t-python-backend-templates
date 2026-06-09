from typing import Protocol


class IUoW(Protocol):
    async def __aenter__(self) -> "IUoW":
        """Open the unit-of-work scope; returns self for `async with`.

        Opens no transaction of its own -- the repositories and this UoW
        share one session, so every write inside the block lands in a single
        atomic transaction committed by __aexit__.
        """
        ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the scope: commit on clean exit, roll back on exception.

        When the block exits without an exception (exc_type is None) the
        session commits; when it exits because an exception is propagating
        the session rolls back and the exception is NOT suppressed. A
        failure of the commit or rollback itself is wrapped in PortError.
        """
        ...
