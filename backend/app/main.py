from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import Settings
from app.models import SmsRequest, SmsResponse
from app.services.monday import MondayClient
from app.services.nimba import NimbaClient

settings = Settings()

app = FastAPI(title="Nimba SMS Monday App Backend")

nimba_client = None
if settings.nimba_sid and settings.nimba_secret:
    nimba_client = NimbaClient(
        base_url=settings.nimba_base_url,
        sid=settings.nimba_sid,
        secret=settings.nimba_secret,
        send_path=settings.nimba_send_path,
        senders_path=settings.nimba_senders_path,
        timeout_seconds=settings.request_timeout_seconds,
    )

monday_client = (
    MondayClient(settings.monday_api_token, settings.request_timeout_seconds)
    if settings.monday_api_token
    else None
)


def _verify_monday_signature(raw_body: bytes, signature: str) -> bool:
    expected = hmac.new(
        settings.monday_signing_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_payload(body: dict[str, Any]) -> dict[str, Any]:
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
    event = body.get("event") if isinstance(body.get("event"), dict) else {}

    phone_number = payload.get("phone_number") or payload.get("phone") or payload.get("to")
    message = payload.get("message") or payload.get("body") or payload.get("text")
    sender_id = payload.get("sender_id") or payload.get("sender")
    nimba_sid = payload.get("nimba_sid") or payload.get("sid")
    nimba_secret = payload.get("nimba_secret") or payload.get("secret")

    board_id = payload.get("board_id") or event.get("boardId")
    item_id = (
        payload.get("item_id")
        or event.get("itemId")
        or event.get("pulseId")
        or event.get("pulse_id")
    )

    status_column_id = payload.get("status_column_id")
    status_label = payload.get("status_label")
    update_body = payload.get("update_body")
    dry_run = bool(payload.get("dry_run", False))

    return {
        "phone_number": phone_number,
        "message": message,
        "sender_id": sender_id,
        "nimba_sid": nimba_sid,
        "nimba_secret": nimba_secret,
        "board_id": int(board_id) if board_id else None,
        "item_id": int(item_id) if item_id else None,
        "status_column_id": status_column_id,
        "status_label": status_label,
        "update_body": update_body,
        "dry_run": dry_run,
    }


def _maybe_update_monday(request_data: SmsRequest, status: str) -> None:
    if not monday_client or not request_data.item_id:
        return

    if request_data.update_body:
        monday_client.create_update(request_data.item_id, request_data.update_body)

    if (
        request_data.board_id
        and request_data.status_column_id
        and request_data.status_label
    ):
        monday_client.change_column_value(
            board_id=request_data.board_id,
            item_id=request_data.item_id,
            column_id=request_data.status_column_id,
            value={"label": request_data.status_label or status},
        )


async def _handle_request(request: Request, signature: str | None) -> SmsResponse:
    raw_body = await request.body()
    if settings.monday_signing_secret:
        if not signature or not _verify_monday_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Signature monday invalide.")

    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="JSON invalide.") from exc

    extracted = _extract_payload(body)
    if not extracted["phone_number"] or not extracted["message"]:
        raise HTTPException(status_code=400, detail="Numéro ou message manquant.")

    sms_request = SmsRequest(**extracted)
    if sms_request.sender_id is None:
        sms_request.sender_id = settings.nimba_sender_id

    if sms_request.dry_run:
        _maybe_update_monday(sms_request, "dry_run")
        return SmsResponse(status="dry_run", nimba_response={"dry_run": True})

    sid = sms_request.nimba_sid or settings.nimba_sid
    secret = sms_request.nimba_secret or settings.nimba_secret
    if not sid or not secret:
        raise HTTPException(
            status_code=400,
            detail="Identifiants Nimba manquants (sid/secret).",
        )

    if (
        nimba_client
        and sid == settings.nimba_sid
        and secret == settings.nimba_secret
    ):
        client = nimba_client
    else:
        client = NimbaClient(
            base_url=settings.nimba_base_url,
            sid=sid,
            secret=secret,
            send_path=settings.nimba_send_path,
            senders_path=settings.nimba_senders_path,
            timeout_seconds=settings.request_timeout_seconds,
        )

    try:
        nimba_response = client.send_sms(
            phone_number=sms_request.phone_number,
            message=sms_request.message,
            sender_id=sms_request.sender_id,
        )
    except Exception as exc:  # noqa: BLE001 - surface real error details
        _maybe_update_monday(sms_request, "failed")
        return SmsResponse(status="error", error=str(exc))

    _maybe_update_monday(sms_request, "sent")
    return SmsResponse(status="sent", nimba_response=nimba_response)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/monday/automation")
async def monday_automation(
    request: Request,
    monday_signature: str | None = Header(None, alias="monday-signature"),
) -> JSONResponse:
    response = await _handle_request(request, monday_signature)
    return JSONResponse(content=response.dict())


@app.post("/monday/action")
async def monday_action(
    request: Request,
    monday_signature: str | None = Header(None, alias="monday-signature"),
) -> JSONResponse:
    response = await _handle_request(request, monday_signature)
    return JSONResponse(content=response.dict())


@app.post("/nimba/dlr")
async def nimba_delivery_report(request: Request) -> dict[str, Any]:
    payload = await request.json()
    return {"status": "received", "payload": payload}


def _normalize_senders(payload: Any) -> list[str]:
    if isinstance(payload, list):
        return [str(value) for value in payload]
    if isinstance(payload, dict):
        for key in ("senders", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [str(item.get("name", item)) for item in value]
    return []


@app.post("/nimba/senders")
async def nimba_senders(request: Request) -> dict[str, Any]:
    body = await request.json()
    sid = body.get("nimba_sid") or body.get("sid") or settings.nimba_sid
    secret = body.get("nimba_secret") or body.get("secret") or settings.nimba_secret

    if not sid or not secret:
        raise HTTPException(
            status_code=400,
            detail="Identifiants Nimba manquants (sid/secret).",
        )

    if (
        nimba_client
        and sid == settings.nimba_sid
        and secret == settings.nimba_secret
    ):
        client = nimba_client
    else:
        client = NimbaClient(
            base_url=settings.nimba_base_url,
            sid=sid,
            secret=secret,
            send_path=settings.nimba_send_path,
            senders_path=settings.nimba_senders_path,
            timeout_seconds=settings.request_timeout_seconds,
        )

    try:
        response = client.list_senders()
    except Exception as exc:  # noqa: BLE001 - surface real error details
        return {"status": "error", "error": str(exc)}

    return {"status": "ok", "senders": _normalize_senders(response), "raw": response}


@app.post("/sendernames")
async def nimba_sendernames_alias(request: Request) -> dict[str, Any]:
    return await nimba_senders(request)
