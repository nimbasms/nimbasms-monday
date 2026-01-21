from __future__ import annotations

from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class NimbaClient:
    def __init__(
        self,
        base_url: str,
        sid: str,
        secret: str,
        send_path: str,
        senders_path: str,
        timeout_seconds: int = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sid = sid
        self.secret = secret
        self.send_path = send_path
        self.senders_path = senders_path
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def send_sms(
        self,
        phone_numbers: list[str],
        message: str,
        sender_id: str | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{self.send_path}"
        payload: dict[str, Any] = {
            "to": phone_numbers,
            "message": message,
        }
        if sender_id:
            payload["sender_name"] = sender_id
        payload["channel"] = "sms"
        if callback_url:
            payload["callback_url"] = callback_url

        response = self.session.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(self.sid, self.secret),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def list_senders(self) -> dict[str, Any]:
        url = f"{self.base_url}{self.senders_path}"
        response = self.session.get(
            url,
            auth=HTTPBasicAuth(self.sid, self.secret),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}
