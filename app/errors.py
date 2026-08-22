from __future__ import annotations

from fastapi.responses import JSONResponse


class SeverityCode:
    """Codes de severite renvoyes a monday quand un bloc d'action echoue.

    monday reessaie pendant 30 minutes toute reponse != 200. Pour une erreur
    definitive (identifiants invalides, numero incorrect), il faut donc signaler
    un echec permanent plutot que laisser la plateforme boucler.

    A VERIFIER avant soumission marketplace : la grille exacte des codes est
    documentee sur https://developer.monday.com/apps/docs/error-handling
    """

    INVALID_INPUT = 4000
    UNAUTHORIZED = 4001
    UPSTREAM_FAILURE = 5000


def action_failure(
    severity_code: int,
    title: str,
    message: str,
    link_to_docs: str | None = None,
) -> JSONResponse:
    """Reponse d'echec pour un bloc d'action, lisible dans l'historique monday."""
    body: dict[str, object] = {
        "severityCode": severity_code,
        "notificationErrorTitle": title,
        "notificationErrorDescription": message,
        "runtimeErrorDescription": message,
    }
    if link_to_docs:
        body["linkToDocs"] = link_to_docs
    return JSONResponse(status_code=400, content=body)
