from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import storage
from app.config import get_settings
from app.phone import normalize_recipients
from app.security import SessionContext, require_account, verify_session_token
from app.services.nimba import NimbaClient, NimbaError, extract_message_ids

router = APIRouter(prefix="/api", tags=["send"])

MAX_RECIPIENTS = 500


class SendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1600)
    recipients: list[str] = Field(min_length=1)
    sender_name: str | None = None
    board_id: str | None = None


class SendResponse(BaseModel):
    sent_count: int
    rejected: list[str]
    message_ids: list[str]


@router.post("/send", response_model=SendResponse)
async def send_now(
    payload: SendRequest,
    context: SessionContext = Depends(verify_session_token),
) -> SendResponse:
    """Envoi manuel declenche depuis la vue de board.

    Authentifie par le sessionToken de la vue, pas par le JWT d'integration :
    la requete vient du navigateur de l'utilisateur, pas du serveur monday.
    """
    account_id = require_account(context)
    if context.is_view_only:
        raise HTTPException(
            status_code=403,
            detail="Votre acces en lecture seule ne permet pas d'envoyer des SMS.",
        )

    credentials = await storage.get_credentials(account_id)
    if not credentials:
        raise HTTPException(
            status_code=409,
            detail="Nimba SMS n'est pas encore connecte a ce compte monday.",
        )

    settings = get_settings()
    recipients, rejected = normalize_recipients(payload.recipients, settings.default_country_code)
    if not recipients:
        raise HTTPException(status_code=400, detail="Aucun numero valide dans la liste.")
    if len(recipients) > MAX_RECIPIENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Envoi limite a {MAX_RECIPIENTS} destinataires a la fois.",
        )

    sender_name = payload.sender_name or credentials.get("default_sender") or None

    try:
        response = await NimbaClient(credentials["sid"], credentials["secret"]).send_sms(
            recipients, payload.message.strip(), sender_name
        )
    except NimbaError as exc:
        raise HTTPException(status_code=502 if not exc.permanent else 400, detail=str(exc)) from exc

    message_ids = extract_message_ids(response)
    for message_id in message_ids:
        await storage.record_message(
            account_id,
            message_id,
            {
                "board_id": payload.board_id,
                "item_id": None,
                "recipients": recipients,
                "sender_name": sender_name,
                "status": "sent",
            },
        )

    return SendResponse(sent_count=len(recipients), rejected=rejected, message_ids=message_ids)
