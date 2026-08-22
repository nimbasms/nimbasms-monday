from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue depuis l'environnement.

    Sur monday code, ces valeurs sont posees avec `mapps code:env` (non sensible)
    ou `mapps code:secret` (sensible). Rien n'est jamais lu depuis le navigateur.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Secrets de l'app monday
    monday_signing_secret: str = ""
    monday_client_secret: str = ""
    monday_client_id: str = ""
    oauth_redirect_uri: str = ""
    app_public_url: str = ""

    # API monday
    monday_api_url: str = "https://api.monday.com/v2"
    monday_api_version: str = "2025-10"

    # API Nimba SMS
    nimba_base_url: str = "https://api.nimbasms.com"
    nimba_send_path: str = "/v1/messages"
    nimba_senders_path: str = "/v1/sendernames"
    nimba_account_path: str = "/v1/accounts"

    request_timeout_seconds: float = 15.0
    default_country_code: str = "224"
    dev_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
