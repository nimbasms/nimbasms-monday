from __future__ import annotations

import httpx

from app.config import get_settings

AUTHORIZE_URL = "https://auth.monday.com/oauth2/authorize"
TOKEN_URL = "https://auth.monday.com/oauth2/token"


class OAuthError(RuntimeError):
    pass


def authorize_url(state: str) -> str:
    """URL vers laquelle rediriger l'admin pour autoriser l'app."""
    settings = get_settings()
    if not settings.monday_client_id:
        raise OAuthError("MONDAY_CLIENT_ID n'est pas configure.")
    from urllib.parse import urlencode

    params = {"client_id": settings.monday_client_id, "state": state}
    if settings.oauth_redirect_uri:
        params["redirect_uri"] = settings.oauth_redirect_uri
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    """Echange le code d'autorisation contre un access token de compte."""
    settings = get_settings()
    if not (settings.monday_client_id and settings.monday_client_secret):
        raise OAuthError("Identifiants OAuth monday incomplets.")

    body = {
        "client_id": settings.monday_client_id,
        "client_secret": settings.monday_client_secret,
        "code": code,
    }
    if settings.oauth_redirect_uri:
        body["redirect_uri"] = settings.oauth_redirect_uri

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(TOKEN_URL, json=body)
    except httpx.HTTPError as exc:
        raise OAuthError(f"Echange OAuth impossible : {exc}") from exc

    if response.status_code >= 400:
        raise OAuthError(f"monday a refuse l'echange OAuth ({response.status_code}).")

    try:
        payload = response.json()
    except ValueError as exc:
        raise OAuthError("Reponse OAuth monday illisible.") from exc

    token = payload.get("access_token")
    if not token:
        raise OAuthError("Aucun access_token dans la reponse OAuth.")
    return str(token)
