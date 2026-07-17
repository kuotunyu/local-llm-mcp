"""Static API-key authentication for the Streamable HTTP transport.

Uses the official SDK's TokenVerifier + AuthSettings mechanism rather than
hand-rolled ASGI middleware: `issuer_url` is a placeholder the SDK never
dereferences (it only appears in the WWW-Authenticate/.well-known metadata),
while `resource_server_url` should be this server's real, reachable URL. See
RESEARCH.md section 2 for the full investigation (including confirmation,
read from the SDK source, that binding host="127.0.0.1" auto-enables Origin/
Host validation — see transport_security in server.py's FastMCP construction).
"""

from __future__ import annotations

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl


class StaticKeyVerifier(TokenVerifier):
    """Accepts exactly one pre-shared API key, compared in constant time."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token, self._api_key):
            return AccessToken(token=token, client_id="local", scopes=[], expires_at=None)
        return None


def build_auth_settings(resource_server_url: str) -> AuthSettings:
    return AuthSettings(
        issuer_url=AnyHttpUrl("https://auth.local-llm-mcp.invalid"),  # placeholder, never dereferenced
        resource_server_url=AnyHttpUrl(resource_server_url),  # real, reachable URL
        required_scopes=None,  # any verified token passes; no scope-based gating
    )
