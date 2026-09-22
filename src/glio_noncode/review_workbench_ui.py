"""Fixed, same-origin static assets for the local review workbench."""

from __future__ import annotations

from importlib.resources import files

_ASSETS = {
    "/": ("web/index.html", "text/html; charset=utf-8"),
    "/workspace": ("web/index.html", "text/html; charset=utf-8"),
    "/workspace/": ("web/index.html", "text/html; charset=utf-8"),
    "/assets/review-workbench.css": ("web/review-workbench.css", "text/css; charset=utf-8"),
    "/assets/review-workbench.js": (
        "web/review-workbench.js",
        "text/javascript; charset=utf-8",
    ),
}

WORKBENCH_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def workbench_asset(path: str) -> tuple[bytes, str] | None:
    """Return one allowlisted packaged asset; never resolve a caller path."""

    asset = _ASSETS.get(path)
    if asset is None:
        return None
    resource, content_type = asset
    body = files("glio_noncode").joinpath(*resource.split("/")).read_bytes()
    return body, content_type


__all__ = ["WORKBENCH_SECURITY_HEADERS", "workbench_asset"]
