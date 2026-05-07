from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: Optional[bool] = None
    last_activity_time: Optional[int] = None

    avatar_url: Optional[str] = None
    full_avatar_url: Optional[str] = None

    name: Optional[str] = None


class Recipient(BaseModel):
    chat_id: int
    chat_type: str

    user_id: Optional[int] = None


class AttachmentPayload(BaseModel):
    photo_id: Optional[int] = None
    token: Optional[str] = None
    url: Optional[str] = None
    fileId: Optional[int] = None


class Attachment(BaseModel):
    type: str
    payload: AttachmentPayload
    filename: Optional[str] = None
    size: Optional[int] = None


class Markup(BaseModel):
    from_: int = Field(alias="from")
    length: int

    type: str
    url: str | None = None
    model_config = {"populate_by_name": True}


class MessageBody(BaseModel):
    mid: str
    seq: int

    text: Optional[str] = None

    attachments: Optional[List[Attachment]] = None

    markup: Optional[List[Markup]] = None


class Message(BaseModel):
    recipient: Recipient
    timestamp: int
    body: MessageBody

    sender: Optional[User] = None


class Update(BaseModel):
    timestamp: Optional[int] = None

    chat_id: Optional[int] = None

    user: Optional[User] = None
    user_id: Optional[int] = None

    user_locale: Optional[str] = None

    is_channel: Optional[bool] = None

    update_type: Literal[
        "bot_started",
        "bot_added",
        "message_created",
    ]

    message: Optional[Message] = None


class LongPollResponse(BaseModel):
    updates: List[Update]
    marker: int
