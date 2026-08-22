from __future__ import annotations

import asyncio
from typing import Any

from app.config import get_settings

_CREDENTIALS_PREFIX = "nimba_credentials"
_MESSAGE_PREFIX = "nimba_message"
_TOKEN_PREFIX = "monday_access_token"


class _InMemoryBackend:
    """Substitut local. Jamais utilise sur monday code (DEV_MODE=false)."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class _SecureStorageBackend:
    """Secure storage monday code, via le SDK Python officiel (`pip install monday-code`).

    Le SDK dialogue avec l'API interne du conteneur sur http://localhost:59999 ;
    les valeurs sont chiffrees au repos et cloisonnees par app.
    """

    def __init__(self) -> None:
        import monday_code

        self._monday_code = monday_code
        self._client = monday_code.ApiClient(monday_code.Configuration())
        self._api = monday_code.SecureStorageApi(self._client)

    def get(self, key: str) -> Any | None:
        try:
            return self._api.get_secure_storage(key).value
        except self._monday_code.ApiException as exc:
            if getattr(exc, "status", None) == 404:
                return None
            raise

    def put(self, key: str, value: Any) -> None:
        contract = self._monday_code.JsonDataContract(value=value)
        self._api.put_secure_storage(key, contract)

    def delete(self, key: str) -> None:
        try:
            self._api.delete_secure_storage(key)
        except self._monday_code.ApiException as exc:
            if getattr(exc, "status", None) != 404:
                raise


_backend: Any | None = None


def _get_backend() -> Any:
    global _backend
    if _backend is None:
        _backend = _InMemoryBackend() if get_settings().dev_mode else _SecureStorageBackend()
    return _backend


def reset_backend(backend: Any | None = None) -> None:
    """Point d'injection pour les tests."""
    global _backend
    _backend = backend


async def _run(func, *args):
    return await asyncio.to_thread(func, *args)


# --- Identifiants Nimba, un jeu par compte monday -------------------------


async def get_credentials(account_id: int) -> dict[str, str] | None:
    value = await _run(_get_backend().get, f"{_CREDENTIALS_PREFIX}:{account_id}")
    if not value or not isinstance(value, dict):
        return None
    if not value.get("sid") or not value.get("secret"):
        return None
    return value


async def save_credentials(account_id: int, sid: str, secret: str, sender_name: str | None) -> None:
    await _run(
        _get_backend().put,
        f"{_CREDENTIALS_PREFIX}:{account_id}",
        {"sid": sid, "secret": secret, "default_sender": sender_name or ""},
    )


async def delete_credentials(account_id: int) -> None:
    await _run(_get_backend().delete, f"{_CREDENTIALS_PREFIX}:{account_id}")


# --- Suivi des messages envoyes ------------------------------------------


async def record_message(account_id: int, message_id: str, data: dict[str, Any]) -> None:
    await _run(_get_backend().put, f"{_MESSAGE_PREFIX}:{account_id}:{message_id}", data)


async def get_message(account_id: int, message_id: str) -> dict[str, Any] | None:
    value = await _run(_get_backend().get, f"{_MESSAGE_PREFIX}:{account_id}:{message_id}")
    return value if isinstance(value, dict) else None


# --- Access token OAuth monday, un par compte ----------------------------


async def save_access_token(account_id: int, token: str) -> None:
    await _run(_get_backend().put, f"{_TOKEN_PREFIX}:{account_id}", {"access_token": token})


async def get_access_token(account_id: int) -> str | None:
    value = await _run(_get_backend().get, f"{_TOKEN_PREFIX}:{account_id}")
    if isinstance(value, dict) and value.get("access_token"):
        return str(value["access_token"])
    return None


async def purge_account(account_id: int) -> None:
    """Efface tout ce qui appartient au compte. Appele a la desinstallation.

    Exigence marketplace : ne rien conserver apres retrait de l'app.
    """
    backend = _get_backend()
    await _run(backend.delete, f"{_CREDENTIALS_PREFIX}:{account_id}")
    await _run(backend.delete, f"{_TOKEN_PREFIX}:{account_id}")
