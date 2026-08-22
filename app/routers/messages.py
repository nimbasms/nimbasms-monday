from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app import storage
from app.security import SessionContext, require_account, verify_session_token
from app.services.monday_api import MondayApiError, MondayClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["messages"])

DELIVERED = {"delivered", "delivrd", "success", "sent_ok"}
FAILED = {"failed", "undeliv", "undelivered", "rejected", "expired"}


def _classify(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in DELIVERED:
        return "delivered"
    if normalized in FAILED:
        return "failed"
    return "pending"


@router.post("/nimba/dlr")
async def delivery_report(request: Request) -> dict[str, str]:
    """Rapport de livraison Nimba SMS.

    Le statut est persiste, puis reporte sur l'element du board quand le compte
    a autorise l'app en OAuth. Le shortLivedToken de l'envoi d'origine a expire
    depuis longtemps : seul un access token de compte permet cette ecriture.
    """
    try:
        payload: Any = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Corps JSON invalide.") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Corps JSON inattendu.")

    message_id = payload.get("messageid") or payload.get("message_id") or payload.get("id")
    account_id = payload.get("account_id")
    raw_status = payload.get("status") or payload.get("state")

    if not message_id or not account_id:
        return {"status": "ignored"}

    account_id = int(account_id)
    record = await storage.get_message(account_id, str(message_id)) or {}
    outcome = _classify(raw_status)
    record.update({"status": outcome, "raw_status": raw_status, "dlr": payload})
    await storage.record_message(account_id, str(message_id), record)

    written = await _report_to_board(account_id, record, outcome)
    return {"status": "recorded", "board_updated": "yes" if written else "no"}


async def _report_to_board(account_id: int, record: dict[str, Any], outcome: str) -> bool:
    item_id = record.get("item_id")
    board_id = record.get("board_id")
    column_id = record.get("dlr_column_id")
    if not (item_id and board_id and column_id):
        return False

    access_token = await storage.get_access_token(account_id)
    if not access_token:
        return False

    label = {"delivered": "Livre", "failed": "Echec", "pending": "En cours"}[outcome]
    try:
        await MondayClient(access_token).set_status(board_id, item_id, str(column_id), label)
    except MondayApiError as exc:
        logger.warning("Report DLR impossible sur l'element %s : %s", item_id, exc)
        return False
    return True


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
