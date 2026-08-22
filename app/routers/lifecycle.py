from __future__ import annotations

from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException, Request

from app import storage
from app.config import get_settings

router = APIRouter(prefix="/monday", tags=["lifecycle"])


@router.post("/lifecycle")
async def lifecycle(request: Request, authorization: str | None = Header(None)) -> dict[str, str]:
    """Webhook de cycle de vie de l'app.

    Contrairement aux requetes d'integration, ces evenements sont signes avec le
    Client Secret. A la desinstallation, on efface tout ce qui appartient au
    compte : identifiants Nimba et access token.
    """
    settings = get_settings()
    if not authorization:
        raise HTTPException(status_code=401, detail="En-tete Authorization manquant.")

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        jwt.decode(
            token,
            settings.monday_client_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Jeton de cycle de vie invalide.") from exc

    try:
        body: Any = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Corps JSON invalide.") from None

    payload = body.get("data") if isinstance(body, dict) else None
    payload = payload if isinstance(payload, dict) else {}
    event_type = (body or {}).get("type") if isinstance(body, dict) else None
    account_id = payload.get("account_id") or payload.get("accountId")

    if event_type in ("uninstall", "app_uninstalled") and account_id:
        await storage.purge_account(int(account_id))
        return {"status": "purged"}

    return {"status": "ok"}
