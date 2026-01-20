from pydantic import BaseModel


class SmsRequest(BaseModel):
    phone_number: str
    message: str
    sender_id: str | None = None
    nimba_sid: str | None = None
    nimba_secret: str | None = None
    board_id: int | None = None
    item_id: int | None = None
    status_column_id: str | None = None
    status_label: str | None = None
    update_body: str | None = None
    dry_run: bool = False


class SmsResponse(BaseModel):
    status: str
    nimba_response: dict | None = None
    error: str | None = None
