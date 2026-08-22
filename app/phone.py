from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[\s\-.()/]")
_DIGITS = re.compile(r"^\d+$")


class InvalidPhoneNumber(ValueError):
    pass


def normalize_msisdn(raw: str, default_country_code: str = "224") -> str:
    """Ramene un numero saisi librement au format international sans '+'.

    Accepte les formes rencontrees sur les boards clients : '+224 622 00 00 00',
    '00224622000000', '622-00-00-00', '(224) 622000000'.
    """
    if raw is None:
        raise InvalidPhoneNumber("Numero vide.")

    cleaned = _SEPARATORS.sub("", str(raw)).strip()
    if not cleaned:
        raise InvalidPhoneNumber("Numero vide.")

    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    elif cleaned.startswith("00"):
        cleaned = cleaned[2:]
    elif not cleaned.startswith(default_country_code):
        cleaned = cleaned.lstrip("0")
        cleaned = f"{default_country_code}{cleaned}"

    if not _DIGITS.match(cleaned):
        raise InvalidPhoneNumber(f"Numero invalide : {raw}")
    if not 8 <= len(cleaned) <= 15:
        raise InvalidPhoneNumber(f"Longueur de numero invalide : {raw}")

    return cleaned


def split_recipients(raw: str | list[str] | None) -> list[str]:
    """Decoupe une cellule de board en numeros individuels."""
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else re.split(r"[\n,;]+", str(raw))
    return [v.strip() for v in values if str(v).strip()]


def normalize_recipients(
    raw: str | list[str] | None, default_country_code: str = "224"
) -> tuple[list[str], list[str]]:
    """Retourne (numeros valides dedupliques, numeros rejetes)."""
    valid: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()

    for candidate in split_recipients(raw):
        try:
            normalized = normalize_msisdn(candidate, default_country_code)
        except InvalidPhoneNumber:
            rejected.append(candidate)
            continue
        if normalized not in seen:
            seen.add(normalized)
            valid.append(normalized)

    return valid, rejected
