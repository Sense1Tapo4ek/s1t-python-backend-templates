from litestar.openapi.spec import Components, SecurityScheme

from ...config import ADMIN_COOKIE_NAME

# Either scheme satisfies a protected operation -- mirrors AuthMiddleware,
# which accepts a bearer Authorization header OR the admin_token cookie.
SECURITY_COMPONENTS = Components(
    security_schemes={
        "bearer": SecurityScheme(type="http", scheme="bearer"),
        "adminCookie": SecurityScheme(
            type="apiKey",
            name=ADMIN_COOKIE_NAME,
            security_scheme_in="cookie",
        ),
    },
)

ADMIN_SECURITY: list[dict[str, list[str]]] = [{"bearer": []}, {"adminCookie": []}]
