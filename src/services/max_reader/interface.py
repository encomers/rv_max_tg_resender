from abc import ABC, abstractmethod
from typing import AsyncIterator

from src.models.requests import SendMessageParams, SendMessageRequest
from src.models.updates import Update


class ILongPoll(ABC):
    @abstractmethod
    def listen(self) -> AsyncIterator[Update]:
        """Бесконечный асинхронный генератор обновлений."""
        ...

    @abstractmethod
    async def send_message(
        self,
        params: SendMessageParams,
        request: SendMessageRequest,
    ) -> None:
        """
        Отправить сообщение пользователю или в чат через Max Platform API.

        :param params: Query-параметры (user_id или chat_id, disable_link_preview)
        :param request: Тело запроса (текст, вложения, форматирование и т.д.)
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Освободить ресурсы."""
        ...
