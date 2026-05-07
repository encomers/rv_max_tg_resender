"""
Модели для исходящих запросов к Max Platform API.

Отделены от src/models/updates.py намеренно:
- updates.py описывает входящие данные (что пришло от API)
- requests.py описывает исходящие данные (что мы отправляем в API)
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Кнопки (inline_keyboard)
# ---------------------------------------------------------------------------


class LinkButton(BaseModel):
    """Кнопка-ссылка."""

    type: Literal["link"] = "link"
    text: str
    url: str


class CallbackButton(BaseModel):
    """Кнопка с callback-payload (для обработки нажатий ботом)."""

    type: Literal["callback"] = "callback"
    text: str
    payload: str


AnyButton = LinkButton | CallbackButton


class InlineKeyboardPayload(BaseModel):
    """Сетка кнопок: список строк, каждая строка — список кнопок."""

    buttons: list[list[AnyButton]]


class InlineKeyboardAttachment(BaseModel):
    """Вложение типа inline_keyboard."""

    type: Literal["inline_keyboard"] = "inline_keyboard"
    payload: InlineKeyboardPayload


# ---------------------------------------------------------------------------
# Медиа-вложения
# ---------------------------------------------------------------------------


class PhotoPayload(BaseModel):
    """
    Payload для вложения image.
    Все поля взаимоисключающие: передавайте ровно одно из трёх.
    - url    — внешний URL изображения
    - token  — токен уже загруженного вложения
    - photos — токены после предварительной загрузки через Upload API
    """

    url: Optional[str] = Field(default=None, min_length=1)
    token: Optional[str] = None
    photos: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def check_exactly_one(self) -> "PhotoPayload":
        filled = sum(v is not None for v in (self.url, self.token, self.photos))
        if filled == 0:
            raise ValueError("PhotoPayload: укажите одно из полей: url, token, photos")
        if filled > 1:
            raise ValueError("PhotoPayload: поля url, token, photos взаимоисключающие")
        return self


class MediaPayload(BaseModel):
    """Payload для video / file — токен или URL."""

    token: Optional[str] = None
    url: Optional[str] = None

    @model_validator(mode="after")
    def check_token_or_url(self) -> "MediaPayload":
        if not self.token and not self.url:
            raise ValueError("MediaPayload: необходимо указать token или url")
        return self


class ImageAttachment(BaseModel):
    type: Literal["image"] = "image"
    payload: PhotoPayload


class VideoAttachment(BaseModel):
    type: Literal["video"] = "video"
    payload: MediaPayload


# ---------------------------------------------------------------------------
# Ссылка на другое сообщение (reply / forward)
# ---------------------------------------------------------------------------


class MessageLink(BaseModel):
    """
    Ссылка на исходное сообщение.

    type="reply"   — ответ на сообщение
    type="forward" — пересылка сообщения
    """

    type: Literal["reply", "forward"]
    mid: str  # ID исходного сообщения


# ---------------------------------------------------------------------------
# Объединённый тип вложения и тело запроса
# ---------------------------------------------------------------------------

AnyAttachment = InlineKeyboardAttachment | ImageAttachment | VideoAttachment


class SendMessageRequest(BaseModel):
    """
    Тело запроса POST /messages.

    Примеры:

    Только текст:
        SendMessageRequest(text="Привет!")

    Текст с кнопкой:
        SendMessageRequest(
            text="Выберите действие",
            attachments=[
                InlineKeyboardAttachment(
                    payload=InlineKeyboardPayload(
                        buttons=[[LinkButton(text="Сайт", url="https://example.com")]]
                    )
                )
            ],
        )

    Ответ на сообщение с HTML-форматированием:
        SendMessageRequest(
            text="<b>Получено!</b>",
            format="html",
            link=MessageLink(type="reply", mid="msg-123"),
        )

    Фото по URL без уведомления:
        SendMessageRequest(
            text="Смотри",
            attachments=[ImageAttachment(payload=PhotoPayload(url="https://..."))],
            notify=False,
        )
    """

    text: Optional[str] = Field(default=None, max_length=4000)
    attachments: Optional[list[AnyAttachment]] = None
    link: Optional[MessageLink] = None
    notify: bool = True
    format: Optional[Literal["markdown", "html"]] = None

    @model_validator(mode="after")
    def check_not_empty(self) -> "SendMessageRequest":
        if not self.text and not self.attachments:
            raise ValueError(
                "SendMessageRequest: сообщение должно содержать text или attachments"
            )
        return self

    def to_api_payload(self) -> dict[str, Any]:
        """Сериализует тело запроса в dict для передачи в aiohttp как json=..."""
        return self.model_dump(exclude_none=True, mode="python")


# ---------------------------------------------------------------------------
# Query-параметры запроса (отдельно от тела)
# ---------------------------------------------------------------------------


class SendMessageParams(BaseModel):
    """
    Query-параметры для POST /messages.
    user_id и chat_id взаимоисключающие — передайте ровно один из двух.
    """

    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    disable_link_preview: Optional[bool] = None

    @model_validator(mode="after")
    def check_recipient(self) -> "SendMessageParams":
        if self.user_id is None and self.chat_id is None:
            raise ValueError(
                "SendMessageParams: укажите user_id (личное сообщение) "
                "или chat_id (сообщение в чат)"
            )
        if self.user_id is not None and self.chat_id is not None:
            raise ValueError("SendMessageParams: user_id и chat_id взаимоисключающие")
        return self

    def to_query(self) -> dict[str, Any]:
        """Сериализует параметры в dict для передачи в aiohttp как params=..."""
        return self.model_dump(exclude_none=True, mode="python")
