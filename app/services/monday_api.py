from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings


class MondayApiError(RuntimeError):
    pass


class MondayClient:
    """Client GraphQL monday.

    Tous les identifiants sont types `ID!`. Depuis la version d'API 2023-10,
    monday a bascule les champs d'identifiants numeriques de `Int` vers `ID` :
    une mutation typee `Int!` est rejetee.

    Le jeton utilise est le `shortLivedToken` extrait du JWT de la requete. Il
    porte les scopes de l'app et vit quelques minutes, ce qui evite de stocker
    un token utilisateur.
    """

    def __init__(self, token: str) -> None:
        settings = get_settings()
        self._url = settings.monday_api_url
        self._timeout = settings.request_timeout_seconds
        self._headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": settings.monday_api_version,
        }

    async def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._url,
                    headers=self._headers,
                    json={"query": query, "variables": variables},
                )
        except httpx.HTTPError as exc:
            raise MondayApiError(f"Appel a l'API monday impossible : {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MondayApiError(f"Reponse monday illisible ({response.status_code}).") from exc

        if payload.get("errors"):
            messages = "; ".join(
                str(err.get("message", err)) for err in payload["errors"] if isinstance(err, dict)
            )
            raise MondayApiError(messages or "Erreur GraphQL monday.")
        return payload.get("data") or {}

    async def get_item_column_values(self, item_id: str | int) -> dict[str, str]:
        query = """
            query ($itemIds: [ID!]) {
              items(ids: $itemIds) {
                id
                name
                column_values { id text }
              }
            }
        """
        data = await self._post(query, {"itemIds": [str(item_id)]})
        items = data.get("items") or []
        if not items:
            return {}
        return {c["id"]: (c.get("text") or "") for c in items[0].get("column_values", [])}

    async def create_update(self, item_id: str | int, body: str) -> None:
        query = """
            mutation ($itemId: ID!, $body: String!) {
              create_update(item_id: $itemId, body: $body) { id }
            }
        """
        await self._post(query, {"itemId": str(item_id), "body": body})

    async def set_status(
        self, board_id: str | int, item_id: str | int, column_id: str, label: str
    ) -> None:
        query = """
            mutation ($boardId: ID!, $itemId: ID!, $columnId: String!, $value: JSON!) {
              change_column_value(
                board_id: $boardId
                item_id: $itemId
                column_id: $columnId
                value: $value
              ) { id }
            }
        """
        await self._post(
            query,
            {
                "boardId": str(board_id),
                "itemId": str(item_id),
                "columnId": column_id,
                "value": json.dumps({"label": label}),
            },
        )
