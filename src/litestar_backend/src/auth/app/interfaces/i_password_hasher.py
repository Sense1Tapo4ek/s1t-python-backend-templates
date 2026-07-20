from typing import Protocol


class IPasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        """Return a self-describing hash (algorithm + params + salt embedded)."""
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """Constant-work check of `password` against `password_hash`.

        False for a mismatch OR a malformed hash -- never raises on bad
        input, so login can call it against a dummy hash to equalize timing
        for unknown emails.
        """
        ...

    def dummy_hash(self) -> str:
        """A valid hash of an unguessable throwaway password.

        Login verifies against this when the email is unknown, keeping the
        unknown-email and wrong-password paths indistinguishable by timing.
        """
        ...
