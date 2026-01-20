from __future__ import annotations

import json
from typing import Any

import requests


class MondayClient:
    def __init__(self, api_token: str, timeout_seconds: int = 15) -> None:
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            "https://api.monday.com/v2",
            json={"query": query, "variables": variables},
            headers={"Authorization": self.api_token},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(payload["errors"])
        return payload.get("data", {})

    def create_update(self, item_id: int, body: str) -> dict[str, Any]:
        query = """
            mutation ($itemId: Int!, $body: String!) {
                create_update(item_id: $itemId, body: $body) { id }
            }
        """
        return self._post(query, {"itemId": item_id, "body": body})

    def change_column_value(
        self,
        board_id: int,
        item_id: int,
        column_id: str,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        query = """
            mutation ($boardId: Int!, $itemId: Int!, $columnId: String!, $value: JSON!) {
                change_column_value(
                    board_id: $boardId,
                    item_id: $itemId,
                    column_id: $columnId,
                    value: $value
                ) {
                    id
                }
            }
        """
        return self._post(
            query,
            {
                "boardId": board_id,
                "itemId": item_id,
                "columnId": column_id,
                "value": json.dumps(value),
            },
        )
