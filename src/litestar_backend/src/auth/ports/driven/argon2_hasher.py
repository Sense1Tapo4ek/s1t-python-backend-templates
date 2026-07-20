import secrets

from pwdlib import PasswordHash


class Argon2Hasher:
    """argon2id via pwdlib's recommended profile; implements IPasswordHasher.

    Single instance per process (provider APP scope): the dummy hash is
    computed once at construction, not per failed login.
    """

    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password, password_hash)
        except Exception:
            return False  # malformed/foreign hash == not a match, never a 500

    def dummy_hash(self) -> str:
        return self._dummy
