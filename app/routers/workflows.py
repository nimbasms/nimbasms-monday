from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app import storage
from app.config import get_settings
from app.errors import SeverityCode, action_failure
from app.phone import normalize_recipients
from app.security import IntegrationContext, verify_integration_request
from app.services.monday_api import MondayApiError, MondayClient
from app.services.nimba import NimbaClient, NimbaError, extract_message_ids

router = APIRouter(prefix="/monday", tags=["workflows"])

CREDENTIALS_HELP = (
    "Ouvrez Admin > Apps > Nimba SMS pour enregistrer vos identifiants Nimba SMS."
)


def _fields(body: dict[str, Any]) -> dict[str, Any]:
    """Extrait les champs configures par l'utilisateur dans le bloc d'action.

    monday envoie la meme donnee sous `inputFields` et `inboundFieldValues`.
    """
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    fields = payload.get("inputFields")
    if not isinstance(fields, dict) or not fields:
        fields = payload.get("inboundFieldValues")
    return fields if isinstance(fields, dict) else {}


def _first(fields: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = fields.get(key)
        if isinstance(value, dict):
            value = value.get("value") or value.get("text") or value.get("label")
        if value not in (None, ""):
            return value
    return None


async def _read_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


@router.post("/action/send-sms")
async def send_sms(
    request: Request,
    context: IntegrationContext = Depends(verify_integration_request),
) -> Response:
    """Run URL du bloc d'action « Envoyer un SMS via Nimba SMS »."""
    settings = get_settings()
    body = await _read_body(request)
    fields = _fields(body)

    if not context.account_id:
        return action_failure(
            SeverityCode.UNAUTHORIZED,
            "Compte monday introuvable",
            "La requete ne contient pas d'identifiant de compte.",
        )

    credentials = await storage.get_credentials(int(context.account_id))
    if not credentials:
        return action_failure(
            SeverityCode.UNAUTHORIZED,
            "Nimba SMS n'est pas connecte",
            CREDENTIALS_HELP,
        )

    message = _first(fields, "messageText", "message", "text")
    if not message or not str(message).strip():
        return action_failure(
            SeverityCode.INVALID_INPUT,
            "Message vide",
            "Le bloc n'a recu aucun texte a envoyer.",
        )
    message = str(message).strip()

    board_id = _first(fields, "boardId", "board_id")
    item_id = _first(fields, "itemId", "item_id", "pulseId")
    raw_recipients = _first(fields, "recipient", "phoneNumber", "phone", "to")
    phone_column_id = _first(fields, "phoneColumnId", "phone_column_id")

    monday_client = MondayClient(context.short_lived_token) if context.short_lived_token else None

    if not raw_recipients and phone_column_id and item_id and monday_client:
        try:
            columns = await monday_client.get_item_column_values(item_id)
        except MondayApiError as exc:
            return action_failure(
                SeverityCode.UPSTREAM_FAILURE,
                "Lecture de l'element impossible",
                str(exc),
            )
        raw_recipients = columns.get(str(phone_column_id), "")

    recipients, rejected = normalize_recipients(raw_recipients, settings.default_country_code)
    if not recipients:
        detail = (
            f"Numeros ignores car illisibles : {', '.join(rejected)}."
            if rejected
            else "Aucun numero de telephone n'a ete trouve pour cet element."
        )
        return action_failure(SeverityCode.INVALID_INPUT, "Aucun destinataire", detail)

    sender_name = _first(fields, "senderName", "sender_name", "sender") or credentials.get(
        "default_sender"
    )

    nimba = NimbaClient(credentials["sid"], credentials["secret"])
    try:
        nimba_response = await nimba.send_sms(recipients, message, sender_name or None)
    except NimbaError as exc:
        severity = (
            SeverityCode.INVALID_INPUT if exc.permanent else SeverityCode.UPSTREAM_FAILURE
        )
        return action_failure(severity, "Envoi du SMS refuse", str(exc))

    message_ids = extract_message_ids(nimba_response)
    for message_id in message_ids:
        await storage.record_message(
            int(context.account_id),
            message_id,
            {
                "board_id": str(board_id) if board_id else None,
                "item_id": str(item_id) if item_id else None,
                "recipients": recipients,
                "sender_name": sender_name,
                "status": "sent",
            },
        )

    if monday_client and item_id:
        await _write_back(monday_client, fields, board_id, item_id, recipients, rejected)

    return JSONResponse(
        content={
            "outputFields": {
                "success": True,
                "recipientCount": len(recipients),
                "rejectedCount": len(rejected),
                "senderName": sender_name or "",
                "messageIds": message_ids,
            }
        }
    )


async def _write_back(
    client: MondayClient,
    fields: dict[str, Any],
    board_id: Any,
    item_id: Any,
    recipients: list[str],
    rejected: list[str],
) -> None:
    """Trace l'envoi sur l'element. Un echec ici ne doit pas rejouer l'envoi."""
    status_column_id = _first(fields, "statusColumnId", "status_column_id")
    status_label = _first(fields, "statusLabel", "status_label")
    log_updates = _first(fields, "logToUpdates")

    if log_updates:
        note = f"SMS envoye a {len(recipients)} destinataire(s) via Nimba SMS."
        if rejected:
            note += f" {len(rejected)} numero(s) ignore(s) : {', '.join(rejected)}."
        try:
            await client.create_update(item_id, note)
        except MondayApiError:
            pass

    if board_id and status_column_id and status_label:
        try:
            await client.set_status(board_id, item_id, str(status_column_id), str(status_label))
        except MondayApiError:
            pass


@router.post("/field-options/senders")
async def sender_name_options(
    context: IntegrationContext = Depends(verify_integration_request),
) -> dict[str, Any]:
    """Remote Options URL : alimente la liste deroulante « expediteur » du bloc."""
    if not context.account_id:
        return {"options": []}

    credentials = await storage.get_credentials(int(context.account_id))
    if not credentials:
        return {"options": []}

    try:
        names = await NimbaClient(credentials["sid"], credentials["secret"]).list_sender_names()
    except NimbaError:
        return {"options": []}

    return {"options": [{"title": name, "value": name} for name in names]}
