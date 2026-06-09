from dataclasses import dataclass

from shared.domain.auth import Principal

from ...app import AuthenticateUc


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthFacade:
    """Driving port for the auth bounded context; serves the admin actor.

    The public entry point for verifying bearer tokens, guarding the boundary
    between the HTTP layer and the authentication use-case logic.
    """

    _authenticate_uc: AuthenticateUc

    async def authenticate(self, token: str) -> Principal | None:
        """Verify a bearer token and return the associated Principal.

        The token is compared in constant time against the configured admin
        credential, so authentication failure leaks no timing signal. This
        method imposes no length limit of its own; the auth middleware caps
        request token length at MAX_TOKEN_LEN before reaching the facade.

        Returns:
            Principal carrying Role.ADMIN when the token matches, or None
            for any invalid, empty, or unrecognised token.

        Raises:
            No exceptions propagate for authentication failures; callers
            receive None and must treat it as an unauthenticated request.
        """
        return await self._authenticate_uc(token)
