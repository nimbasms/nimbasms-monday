from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, Request

from app.config import get_settings

ALGORITHMS = ["HS256"]


@dataclass(frozen=True)
class IntegrationContext:
    """Contenu du JWT envoye par le serveur d'automatisation monday."""

    account_id: int | None
    user_id: int | None
    short_lived_token: str | None


@dataclass(frozen=True)
class SessionContext:
    """Contenu du sessionToken emis cote client par `monday.get('sessionToken')`."""

    account_id: int | None
    user_id: int | None
    is_admin: bool
    is_view_only: bool


def _strip_bearer(value: str) -> str:
    prefix = "bearer "
    return value[len(prefix) :].strip() if value.lower().startswith(prefix) else value.strip()


def _decode(token: str, secret: str, *, audience: str | None) -> dict:
    options = {"verify_aud": bool(audience)}
    return jwt.decode(
        token,
        secret,
        algorithms=ALGORITHMS,
        audience=audience if audience else None,
        options=options,
    )


def verify_integration_request(
    request: Request,
    authorization: str | None = Header(None),
) -> IntegrationContext:
    """Valide une requete serveur-a-serveur venant de monday.

    Le JWT est signe avec le Signing Secret de l'app. On verifie la signature,
    l'expiration, et l'audience quand APP_PUBLIC_URL est renseigne.
    """
    settings = get_settings()

    if not settings.monday_signing_secret:
        raise HTTPException(
            status_code=500,
            detail="MONDAY_SIGNING_SECRET n'est pas configure sur le serveur.",
        )
    if not authorization:
        raise HTTPException(status_code=401, detail="En-tete Authorization manquant.")

    audience = None
    if settings.app_public_url:
        audience = f"{settings.app_public_url.rstrip('/')}{request.url.path}"

    try:
        claims = _decode(_strip_bearer(authorization), settings.monday_signing_secret, audience=audience)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Jeton monday expire.") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(status_code=401, detail="Audience du jeton monday inattendue.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Jeton monday invalide.") from exc

    return IntegrationContext(
        account_id=claims.get("accountId"),
        user_id=claims.get("userId"),
        short_lived_token=claims.get("shortLivedToken"),
    )


def verify_session_token(authorization: str | None = Header(None)) -> SessionContext:
    """Valide le sessionToken envoye par une vue de l'app.

    La doc monday indique que ce jeton est signe avec le Client Secret, mais
    plusieurs apps rapportent une signature avec le Signing Secret selon le type
    de vue. On accepte donc les deux secrets configures, ce qui evite un echec
    silencieux sans elargir la surface d'attaque.
    """
    settings = get_settings()

    if not authorization:
        raise HTTPException(status_code=401, detail="Session monday manquante.")

    token = _strip_bearer(authorization)
    secrets = [s for s in (settings.monday_client_secret, settings.monday_signing_secret) if s]
    if not secrets:
        raise HTTPException(
            status_code=500,
            detail="Aucun secret monday configure sur le serveur.",
        )

    claims: dict | None = None
    expired = False
    for secret in secrets:
        try:
            claims = _decode(token, secret, audience=None)
            break
        except jwt.ExpiredSignatureError:
            expired = True
        except jwt.InvalidTokenError:
            continue

    if claims is None:
        detail = "Session monday expiree." if expired else "Session monday invalide."
        raise HTTPException(status_code=401, detail=detail)

    data = claims.get("dat") or claims
    return SessionContext(
        account_id=data.get("account_id") or data.get("accountId"),
        user_id=data.get("user_id") or data.get("userId"),
        is_admin=bool(data.get("is_admin", False)),
        is_view_only=bool(data.get("is_view_only", False)),
    )


def require_account(context: SessionContext) -> int:
    if not context.account_id:
        raise HTTPException(status_code=401, detail="Compte monday introuvable dans la session.")
    return int(context.account_id)
