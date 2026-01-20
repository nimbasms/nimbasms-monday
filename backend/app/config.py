from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    nimba_base_url: str = Field(..., env="NIMBA_BASE_URL")
    nimba_sid: str | None = Field(None, env="NIMBA_SID")
    nimba_secret: str | None = Field(None, env="NIMBA_SECRET")
    nimba_sender_id: str | None = Field(None, env="NIMBA_SENDER_ID")
    nimba_send_path: str = Field("/v1/messages", env="NIMBA_SEND_PATH")
    nimba_senders_path: str = Field("/v1/sendernames", env="NIMBA_SENDERS_PATH")

    monday_api_token: str | None = Field(None, env="MONDAY_API_TOKEN")
    monday_signing_secret: str | None = Field(None, env="MONDAY_SIGNING_SECRET")

    request_timeout_seconds: int = Field(15, env="REQUEST_TIMEOUT_SECONDS")

    class Config:
        case_sensitive = True
