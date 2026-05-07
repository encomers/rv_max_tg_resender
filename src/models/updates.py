"""
Pydantic-модели входящих данных Max Platform API.

Соответствуют схемам из официальной документации:
https://dev.max.ru/docs-api
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Пользователь
# ---------------------------------------------------------------------------


class User(BaseModel):
    user_id: int
    first_name: str
    last_name: Optional[str] = None  # Nullable optional; у ботов не возвращается
    username: Optional[str] = None  # Nullable; может отсутствовать у пользователей
    is_bot: bool = False
    last_activity_time: Optional[int] = (
        None  # Unix ms; может отсутствовать по настройкам приватности
    )
    name: Optional[str] = None  # Deprecated, будет удалено


# ---------------------------------------------------------------------------
# Получатель
# ---------------------------------------------------------------------------


class Recipient(BaseModel):
    chat_id: Optional[int] = None  # Nullable согласно спецификации
    chat_type: Literal[
        "chat", "channel", "dialog"
    ]  # Единственный возможный вариант по документации
    user_id: Optional[int] = None  # ID пользователя, если ЛС


# ---------------------------------------------------------------------------
# Вложения
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Разметка текста
# ---------------------------------------------------------------------------


class MarkupElement(BaseModel):
    """Один элемент разметки текста сообщения."""

    from_: int = Field(alias="from")  # позиция начала в тексте
    length: int
    type: str  # strong, emphasized, link, monospaced, ...
    url: Optional[str] = None  # только для type="link"

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Тело сообщения
# ---------------------------------------------------------------------------


class MessageBody(BaseModel):
    mid: str  # уникальный ID сообщения
    seq: int  # порядковый номер в чате
    text: Optional[str] = None  # Nullable
    attachments: Optional[List[Attachment]] = None  # Nullable optional
    markup: Optional[List[MarkupElement]] = None  # Nullable optional


# ---------------------------------------------------------------------------
# Статистика сообщения (только для постов в каналах)
# ---------------------------------------------------------------------------


class MessageStat(BaseModel):
    views: int  # количество просмотров поста


# ---------------------------------------------------------------------------
# Связанное сообщение (reply / forward)
# ---------------------------------------------------------------------------


class LinkedMessage(BaseModel):
    """
    Пересланное или ответное сообщение внутри Message.

    type="reply"   — ответ на сообщение
    type="forward" — пересланное сообщение
    """

    type: Literal["reply", "forward"]
    sender: Optional[User] = None  # автор исходного сообщения
    chat_id: Optional[int] = None  # чат публикации; только для forward
    message: MessageBody


# ---------------------------------------------------------------------------
# Сообщение
# ---------------------------------------------------------------------------


class Message(BaseModel):
    recipient: Recipient
    timestamp: int  # Unix-время создания
    body: MessageBody
    sender: Optional[User] = None  # отсутствует у анонимных сообщений
    link: Optional[LinkedMessage] = None  # Nullable optional; reply или forward
    stat: Optional[MessageStat] = None  # Nullable optional; только для постов в каналах
    url: Optional[str] = None  # Nullable optional; публичная ссылка на пост


# ---------------------------------------------------------------------------
# Обновление
# ---------------------------------------------------------------------------


class Update(BaseModel):
    update_type: Literal[
        "bot_started",
        "bot_added",
        "message_created",
    ]
    timestamp: Optional[int] = None  # Unix-время события
    message: Optional[Message] = None

    # Поля, возвращаемые в зависимости от update_type
    chat_id: Optional[int] = None
    user: Optional[User] = None
    user_id: Optional[int] = None
    user_locale: Optional[str] = None  # IETF BCP 47; только в диалогах
    is_channel: Optional[bool] = None


# ---------------------------------------------------------------------------
# Ответ Long Poll
# ---------------------------------------------------------------------------


class LongPollResponse(BaseModel):
    updates: List[Update]
    marker: int  # Nullable в доке, но нужен для следующего запроса
