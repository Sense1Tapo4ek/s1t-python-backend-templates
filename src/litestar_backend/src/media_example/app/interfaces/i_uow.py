from typing import Protocol


class IUoW(Protocol):
    async def __aenter__(self) -> "IUoW":
        """Open the unit-of-work scope; returns self for `async with`.

        Opens no new transaction of its own -- it commits or rolls back
        the session that the repositories already share, so every write
        inside the block lands in one atomic transaction.
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
