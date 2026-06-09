from dataclasses import dataclass

from shared.domain.auth import Principal

from ...app import AuthenticateUc


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthFacade:
    """Driving port for the auth bounded context; serves the admin actor.

    This is the only public entry point other contexts and driving adapters
    (middleware, guards) use to verify bearer tokens. It enforces the
    boundary between the HTTP layer and the authentication use-case logic.
    """

    _authenticate_uc: AuthenticateUc

    async def authenticate(self, token: str) -> Principal | None:
        """Verify a bearer token and return the associated Principal.

        Delegates to AuthenticateUc, which uses ITokenResolver (currently
        StaticTokenResolver). The resolver performs constant-time comparison
        against the configured admin token, so this method is safe to call
        with untrusted input of arbitrary length up to MAX_TOKEN_LEN.

        Returns:
            Principal carrying Role.ADMIN when the token matches, or None
            for any invalid, empty, or unrecognised token.

        Raises:
            No exceptions propagate for authentication failures; callers
            receive None and must treat it as an unauthenticated request.
        """
        return await self._authenticate_uc(token)
