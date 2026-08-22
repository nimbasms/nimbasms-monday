from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app import storage
from app.security import SessionContext, require_account, verify_session_token
from app.services.nimba import NimbaClient, NimbaError

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


class CredentialsPayload(BaseModel):
    sid: str = Field(min_length=1)
    secret: str = Field(min_length=1)
    default_sender: str | None = None


class CredentialsStatus(BaseModel):
    configured: bool
    default_sender: str = ""
    sender_names: list[str] = []


@router.get("", response_model=CredentialsStatus)
async def read_status(
    context: SessionContext = Depends(verify_session_token),
) -> CredentialsStatus:
    account_id = require_account(context)
    credentials = await storage.get_credentials(account_id)
    if not credentials:
        return CredentialsStatus(configured=False)

    try:
        names = await NimbaClient(credentials["sid"], credentials["secret"]).list_sender_names()
    except NimbaError:
        names = []

    return CredentialsStatus(
        configured=True,
        default_sender=credentials.get("default_sender", ""),
        sender_names=names,
    )


@router.put("", response_model=CredentialsStatus)
async def save(
    payload: CredentialsPayload,
    context: SessionContext = Depends(verify_session_token),
) -> CredentialsStatus:
    """Enregistre les identifiants Nimba du compte, apres validation.

    Reserve aux administrateurs : ces identifiants engagent le credit SMS de
    toute l'organisation.
    """
    account_id = require_account(context)
    if not context.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Seul un administrateur du compte peut connecter Nimba SMS.",
        )

    client = NimbaClient(payload.sid.strip(), payload.secret.strip())
    try:
        await client.verify()
        names = await client.list_sender_names()
    except NimbaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    default_sender = payload.default_sender or ""
    if default_sender and names and default_sender not in names:
        raise HTTPException(
            status_code=400,
            detail=f"L'expediteur « {default_sender} » n'existe pas sur ce compte Nimba SMS.",
        )

    await storage.save_credentials(
        account_id, payload.sid.strip(), payload.secret.strip(), default_sender
    )
    return CredentialsStatus(configured=True, default_sender=default_sender, sender_names=names)


@router.delete("", status_code=204, response_class=Response)
async def remove(context: SessionContext = Depends(verify_session_token)) -> Response:
    account_id = require_account(context)
    if not context.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Seul un administrateur du compte peut deconnecter Nimba SMS.",
        )
    await storage.delete_credentials(account_id)
    return Response(status_code=204)
