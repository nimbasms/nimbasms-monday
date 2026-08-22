from __future__ import annotations

import os

os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("MONDAY_SIGNING_SECRET", "signing-secret-for-tests")
os.environ.setdefault("MONDAY_CLIENT_SECRET", "client-secret-for-tests")

import jwt
import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.phone import normalize_msisdn, normalize_recipients
from app.services.nimba import extract_message_ids, normalize_sender_names

SIGNING_SECRET = "signing-secret-for-tests"
CLIENT_SECRET = "client-secret-for-tests"
ACCOUNT_ID = 1825529


@pytest.fixture(autouse=True)
def _fresh_storage():
    storage.reset_backend(storage._InMemoryBackend())
    yield
    storage.reset_backend(None)


@pytest.fixture
def client():
    return TestClient(app)


def integration_token(**overrides):
    claims = {
        "accountId": ACCOUNT_ID,
        "userId": 4012689,
        "shortLivedToken": "short-lived",
        "exp": 9999999999,
    }
    claims.update(overrides)
    return jwt.encode(claims, SIGNING_SECRET, algorithm="HS256")


def session_token(is_admin=True):
    claims = {
        "dat": {"account_id": ACCOUNT_ID, "user_id": 4012689, "is_admin": is_admin},
        "exp": 9999999999,
    }
    return jwt.encode(claims, CLIENT_SECRET, algorithm="HS256")


# --- normalisation des numeros -------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+224 622 00 00 00", "224622000000"),
        ("00224622000000", "224622000000"),
        ("622-00-00-00", "224622000000"),
        ("(224) 622000000", "224622000000"),
        ("0622000000", "224622000000"),
    ],
)
def test_normalize_msisdn(raw, expected):
    assert normalize_msisdn(raw) == expected


def test_normalize_recipients_dedupes_and_reports_rejects():
    valid, rejected = normalize_recipients("+224622000000, 622000000\nabc")
    assert valid == ["224622000000"]
    assert rejected == ["abc"]


# --- parsing des reponses Nimba ------------------------------------------


def test_sender_names_filters_unapproved():
    payload = {"results": [{"name": "NIMBA", "status": "accepted"}, {"name": "TEST", "status": "pending"}]}
    assert normalize_sender_names(payload) == ["NIMBA"]


def test_extract_message_ids_from_nested_payload():
    assert extract_message_ids({"data": {"messageid": "abc-123"}}) == ["abc-123"]


# --- securite -------------------------------------------------------------


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_action_rejects_missing_token(client):
    response = client.post("/monday/action/send-sms", json={"payload": {}})
    assert response.status_code == 401


def test_action_rejects_forged_token(client):
    forged = jwt.encode({"accountId": ACCOUNT_ID, "exp": 9999999999}, "wrong", algorithm="HS256")
    response = client.post(
        "/monday/action/send-sms",
        json={"payload": {}},
        headers={"Authorization": forged},
    )
    assert response.status_code == 401


def test_credentials_require_admin(client):
    response = client.put(
        "/api/credentials",
        json={"sid": "x", "secret": "y"},
        headers={"Authorization": session_token(is_admin=False)},
    )
    assert response.status_code == 403


# --- bloc d'action --------------------------------------------------------


def test_action_reports_missing_credentials(client):
    response = client.post(
        "/monday/action/send-sms",
        json={"payload": {"inputFields": {"messageText": "Bonjour", "recipient": "622000000"}}},
        headers={"Authorization": integration_token()},
    )
    assert response.status_code == 400
    assert response.json()["notificationErrorTitle"] == "Nimba SMS n'est pas connecte"


def test_action_reads_input_fields_and_sends(client, monkeypatch):
    storage._get_backend().put(
        f"nimba_credentials:{ACCOUNT_ID}",
        {"sid": "sid", "secret": "secret", "default_sender": "NIMBA"},
    )
    captured = {}

    async def fake_send(self, recipients, message, sender_name=None, callback_url=None):
        captured.update(recipients=recipients, message=message, sender_name=sender_name)
        return {"messageid": "msg-1"}

    monkeypatch.setattr("app.services.nimba.NimbaClient.send_sms", fake_send)

    response = client.post(
        "/monday/action/send-sms",
        json={
            "payload": {
                "inputFields": {
                    "messageText": "Votre colis est arrive",
                    "recipient": "+224 622 00 00 00",
                    "senderName": "NIMBA",
                }
            }
        },
        headers={"Authorization": integration_token()},
    )

    assert response.status_code == 200
    assert response.json()["outputFields"]["recipientCount"] == 1
    assert captured["recipients"] == ["224622000000"]
    assert captured["sender_name"] == "NIMBA"


def test_action_falls_back_to_inbound_field_values(client, monkeypatch):
    storage._get_backend().put(
        f"nimba_credentials:{ACCOUNT_ID}", {"sid": "s", "secret": "x", "default_sender": ""}
    )

    async def fake_send(self, recipients, message, sender_name=None, callback_url=None):
        return {"messageid": "msg-2"}

    monkeypatch.setattr("app.services.nimba.NimbaClient.send_sms", fake_send)

    response = client.post(
        "/monday/action/send-sms",
        json={
            "payload": {
                "inboundFieldValues": {"messageText": "Rappel", "recipient": "622000001"}
            }
        },
        headers={"Authorization": integration_token()},
    )
    assert response.status_code == 200


def test_action_rejects_empty_message(client):
    storage._get_backend().put(
        f"nimba_credentials:{ACCOUNT_ID}", {"sid": "s", "secret": "x", "default_sender": ""}
    )
    response = client.post(
        "/monday/action/send-sms",
        json={"payload": {"inputFields": {"recipient": "622000000"}}},
        headers={"Authorization": integration_token()},
    )
    assert response.status_code == 400
    assert response.json()["severityCode"] == 4000


def test_action_surfaces_permanent_nimba_error_without_retry(client, monkeypatch):
    from app.services.nimba import NimbaError

    storage._get_backend().put(
        f"nimba_credentials:{ACCOUNT_ID}", {"sid": "s", "secret": "x", "default_sender": ""}
    )

    async def fake_send(self, recipients, message, sender_name=None, callback_url=None):
        raise NimbaError("Identifiants Nimba SMS refuses.", status_code=401, permanent=True)

    monkeypatch.setattr("app.services.nimba.NimbaClient.send_sms", fake_send)

    response = client.post(
        "/monday/action/send-sms",
        json={"payload": {"inputFields": {"messageText": "Hi", "recipient": "622000000"}}},
        headers={"Authorization": integration_token()},
    )
    assert response.status_code == 400
    assert response.json()["severityCode"] == 4000


def test_cors_allows_monday_origin(client):
    response = client.options(
        "/api/credentials",
        headers={
            "Origin": "https://acme.monday.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "https://acme.monday.com"


# --- envoi manuel depuis la vue -------------------------------------------


def test_manual_send_requires_credentials(client):
    response = client.post(
        "/api/send",
        json={"message": "Bonjour", "recipients": ["622000000"]},
        headers={"Authorization": session_token()},
    )
    assert response.status_code == 409


def test_manual_send_normalizes_and_reports_rejects(client, monkeypatch):
    storage._get_backend().put(
        f"nimba_credentials:{ACCOUNT_ID}",
        {"sid": "sid", "secret": "secret", "default_sender": "NIMBA"},
    )

    async def fake_send(self, recipients, message, sender_name=None, callback_url=None):
        return {"messageid": "msg-9"}

    monkeypatch.setattr("app.services.nimba.NimbaClient.send_sms", fake_send)

    response = client.post(
        "/api/send",
        json={"message": "Bonjour", "recipients": ["+224622000000", "622000000", "oops"]},
        headers={"Authorization": session_token()},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["sent_count"] == 1
    assert body["rejected"] == ["oops"]
    assert body["message_ids"] == ["msg-9"]


def test_manual_send_rejects_view_only_user(client):
    token = jwt.encode(
        {
            "dat": {"account_id": ACCOUNT_ID, "user_id": 1, "is_view_only": True},
            "exp": 9999999999,
        },
        CLIENT_SECRET,
        algorithm="HS256",
    )
    response = client.post(
        "/api/send",
        json={"message": "Bonjour", "recipients": ["622000000"]},
        headers={"Authorization": token},
    )
    assert response.status_code == 403


# --- rapports de livraison et cycle de vie --------------------------------


def test_dlr_ignores_payload_without_identifiers(client):
    response = client.post("/nimba/dlr", json={"status": "DELIVRD"})
    assert response.json()["status"] == "ignored"


def test_dlr_records_status_without_oauth_token(client):
    storage._get_backend().put(
        f"nimba_message:{ACCOUNT_ID}:msg-1",
        {"board_id": "1", "item_id": "2", "dlr_column_id": "status", "status": "sent"},
    )
    response = client.post(
        "/nimba/dlr",
        json={"messageid": "msg-1", "account_id": ACCOUNT_ID, "status": "DELIVRD"},
    )
    body = response.json()
    assert body["status"] == "recorded"
    assert body["board_updated"] == "no"  # pas de token OAuth pour ce compte

    stored = storage._get_backend().get(f"nimba_message:{ACCOUNT_ID}:msg-1")
    assert stored["status"] == "delivered"


def test_dlr_writes_back_to_board_when_authorized(client, monkeypatch):
    storage._get_backend().put(
        f"monday_access_token:{ACCOUNT_ID}", {"access_token": "oauth-token"}
    )
    storage._get_backend().put(
        f"nimba_message:{ACCOUNT_ID}:msg-2",
        {"board_id": "10", "item_id": "20", "dlr_column_id": "statut", "status": "sent"},
    )
    captured = {}

    async def fake_set_status(self, board_id, item_id, column_id, label):
        captured.update(board_id=board_id, item_id=item_id, column_id=column_id, label=label)

    monkeypatch.setattr("app.services.monday_api.MondayClient.set_status", fake_set_status)

    response = client.post(
        "/nimba/dlr",
        json={"messageid": "msg-2", "account_id": ACCOUNT_ID, "status": "UNDELIV"},
    )
    assert response.json()["board_updated"] == "yes"
    assert captured["label"] == "Echec"
    assert captured["column_id"] == "statut"


def test_lifecycle_purges_account_on_uninstall(client):
    storage._get_backend().put(
        f"nimba_credentials:{ACCOUNT_ID}", {"sid": "s", "secret": "x", "default_sender": ""}
    )
    storage._get_backend().put(f"monday_access_token:{ACCOUNT_ID}", {"access_token": "t"})

    token = jwt.encode({"exp": 9999999999}, CLIENT_SECRET, algorithm="HS256")
    response = client.post(
        "/monday/lifecycle",
        json={"type": "uninstall", "data": {"account_id": ACCOUNT_ID}},
        headers={"Authorization": token},
    )
    assert response.json()["status"] == "purged"
    assert storage._get_backend().get(f"nimba_credentials:{ACCOUNT_ID}") is None
    assert storage._get_backend().get(f"monday_access_token:{ACCOUNT_ID}") is None


def test_lifecycle_rejects_signing_secret(client):
    forged = jwt.encode({"exp": 9999999999}, SIGNING_SECRET, algorithm="HS256")
    response = client.post(
        "/monday/lifecycle",
        json={"type": "uninstall", "data": {"account_id": ACCOUNT_ID}},
        headers={"Authorization": forged},
    )
    assert response.status_code == 401


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
