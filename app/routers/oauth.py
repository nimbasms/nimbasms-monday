from __future__ import annotations

import secrets

import jwt
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app import storage
from app.config import get_settings
from app.services.monday_oauth import OAuthError, exchange_code

router = APIRouter(prefix="/oauth", tags=["oauth"])

_CONFIRMATION = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Nimba SMS</title></head>
<body style="font-family:Figtree,Roboto,sans-serif;padding:32px;color:#323338">
<h1 style="font-size:20px">Autorisation accordee</h1>
<p style="color:#676879">Vous pouvez fermer cet onglet et revenir sur monday.com.</p>
</body></html>"""


@router.get("/install")
async def install(token: str = Query(...)) -> RedirectResponse:
    """Point d'entree de l'installation depuis le Developer Center.

    monday passe un JWT signe avec le Signing Secret. On le verifie avant de
    rediriger vers l'ecran d'autorisation.
    """
    settings = get_settings()
    try:
        jwt.decode(
            token,
            settings.monday_signing_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Jeton d'installation invalide.") from exc

    from app.services.monday_oauth import authorize_url

    return RedirectResponse(authorize_url(state=token or secrets.token_urlsafe(16)))


@router.get("/callback")
async def callback(code: str = Query(...), state: str = Query("")) -> HTMLResponse:
    """Recoit le code d'autorisation et conserve l'access token du compte.

    Ce jeton sert uniquement aux ecritures differees (rapports de livraison),
    quand le shortLivedToken de la requete d'origine a deja expire.
    """
    settings = get_settings()

    account_id = None
    if state:
        try:
            claims = jwt.decode(
                state,
                settings.monday_signing_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            account_id = claims.get("accountId") or claims.get("account_id")
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail="Etat OAuth invalide.") from exc

    if not account_id:
        raise HTTPException(status_code=400, detail="Compte monday absent de l'etat OAuth.")

    try:
        access_token = await exchange_code(code)
    except OAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await storage.save_access_token(int(account_id), access_token)
    return HTMLResponse(_CONFIRMATION)
