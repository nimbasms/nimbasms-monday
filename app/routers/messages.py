from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app import storage
from app.security import SessionContext, require_account, verify_session_token

router = APIRouter(tags=["messages"])


@router.post("/nimba/dlr")
async def delivery_report(request: Request) -> dict[str, str]:
    """Accuse de reception des rapports de livraison Nimba SMS.

    Le statut est conserve pour etre relu par la vue. L'ecriture differee sur
    le board n'est pas faite ici : a ce stade le shortLivedToken de la requete
    d'origine a expire, il faudrait un access token OAuth obtenu a l'install.
    Voir la section « Limites connues » du README.
    """
    try:
        payload: Any = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Corps JSON invalide.") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Corps JSON inattendu.")

    message_id = payload.get("messageid") or payload.get("message_id") or payload.get("id")
    account_id = payload.get("account_id")
    status = payload.get("status") or payload.get("state")

    if not message_id or not account_id:
        return {"status": "ignored"}

    existing = await storage.get_message(int(account_id), str(message_id)) or {}
    existing.update({"status": status or "unknown", "dlr": payload})
    await storage.record_message(int(account_id), str(message_id), existing)
    return {"status": "recorded"}


@router.get("/api/messages/{message_id}")
async def read_message(
    message_id: str,
    context: SessionContext = Depends(verify_session_token),
) -> dict[str, Any]:
    account_id = require_account(context)
    record = await storage.get_message(account_id, message_id)
    if not record:
        raise HTTPException(status_code=404, detail="Message inconnu.")
    return record
