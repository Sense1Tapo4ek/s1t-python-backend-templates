from typing import Protocol

from shared.domain.auth import Principal


class ITokenResolver(Protocol):
    async def resolve(self, token: str) -> Principal | None:
        """Verify *token* and return the matching Principal, or None.

        Implementations MUST use constant-time comparison to prevent
        timing-oracle attacks (see StaticTokenResolver). Oversize-input
        rejection is the caller's responsibility: the auth middleware caps
        token length at MAX_TOKEN_LEN before this method is reached, so the
        resolver itself imposes no length limit.

        Returns:
            Principal with the role granted by the token, or None when the
            token is absent, empty, or does not match any known credential.

        Raises:
            No exceptions are raised for invalid tokens; callers receive None.
            Infrastructure failures (e.g. unreachable secret store) may raise
            PortError subclasses in future implementations.
        """
        ...
