from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class NimbaError(RuntimeError):
    """Echec cote API Nimba SMS."""

    def __init__(self, message: str, *, status_code: int | None = None, permanent: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.permanent = permanent


class NimbaClient:
    """Client asynchrone de l'API Nimba SMS (auth Basic sid / secret)."""

    def __init__(self, sid: str, secret: str) -> None:
        settings = get_settings()
        self._base_url = settings.nimba_base_url.rstrip("/")
        self._send_path = settings.nimba_send_path
        self._senders_path = settings.nimba_senders_path
        self._account_path = settings.nimba_account_path
        self._auth = httpx.BasicAuth(sid, secret)
        self._timeout = settings.request_timeout_seconds

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, auth=self._auth) as client:
                response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise NimbaError("L'API Nimba SMS n'a pas repondu dans le delai imparti.") from exc
        except httpx.HTTPError as exc:
            raise NimbaError(f"Contact impossible avec l'API Nimba SMS : {exc}") from exc

        if response.status_code in (401, 403):
            raise NimbaError(
                "Identifiants Nimba SMS refuses.",
                status_code=response.status_code,
                permanent=True,
            )
        if response.status_code == 402:
            raise NimbaError(
                "Credit Nimba SMS insuffisant.",
                status_code=response.status_code,
                permanent=True,
            )
        if 400 <= response.status_code < 500:
            raise NimbaError(
                f"Requete refusee par Nimba SMS ({response.status_code}) : {response.text[:300]}",
                status_code=response.status_code,
                permanent=True,
            )
        if response.status_code >= 500:
            raise NimbaError(
                f"Erreur serveur Nimba SMS ({response.status_code}).",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError:
            return {"raw": response.text}
        return payload if isinstance(payload, dict) else {"data": payload}

    async def send_sms(
        self,
        recipients: list[str],
        message: str,
        sender_name: str | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"to": recipients, "message": message}
        if sender_name:
            body["sender_name"] = sender_name
        if callback_url:
            body["callback_url"] = callback_url
        return await self._request("POST", self._send_path, json=body)

    async def list_sender_names(self) -> list[str]:
        payload = await self._request("GET", self._senders_path)
        return normalize_sender_names(payload)

    async def verify(self) -> None:
        """Valide un couple sid/secret. Leve NimbaError s'il est refuse."""
        await self._request("GET", self._account_path)


def normalize_sender_names(payload: Any) -> list[str]:
    """Extrait les noms d'expediteur, quelle que soit l'enveloppe renvoyee."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = None
        for key in ("results", "sendernames", "senders", "data"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        if items is None:
            return []
    else:
        return []

    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("name") or item.get("sender_name") or item.get("sendername") or ""
            status = str(item.get("status", "")).lower()
            if status and status not in ("accepted", "active", "approved", "valid"):
                continue
        else:
            continue
        if name and name not in names:
            names.append(name)
    return names


def extract_message_ids(payload: Any) -> list[str]:
    """Recupere les identifiants de messages depuis une reponse d'envoi."""
    if not isinstance(payload, dict):
        return []
    for key in ("messageid", "message_id", "id"):
        if payload.get(key):
            return [str(payload[key])]
    for key in ("data", "results", "messages"):
        block = payload.get(key)
        if isinstance(block, dict):
            for sub in ("messageid", "message_id", "id"):
                if block.get(sub):
                    return [str(block[sub])]
        if isinstance(block, list):
            ids = []
            for entry in block:
                if isinstance(entry, dict):
                    for sub in ("messageid", "message_id", "id"):
                        if entry.get(sub):
                            ids.append(str(entry[sub]))
                            break
            if ids:
                return ids
    return []
