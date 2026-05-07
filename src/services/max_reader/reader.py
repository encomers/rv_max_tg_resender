import asyncio
import logging
from typing import AsyncIterator

import aiohttp
from aiohttp import ClientError, ServerTimeoutError

from src.models.requests import SendMessageParams, SendMessageRequest
from src.models.updates import LongPollResponse, Update

from .interface import ILongPoll

logger = logging.getLogger(__name__)


class LongPoll(ILongPoll):
    """
    Production-ready long poll клиент для Max Platform API.

    Пример использования:
        async with LongPoll(base_url=BASE_URL, token=TOKEN) as lp:
            async for update in lp.listen():
                ...
    """

    _RETRY_DELAYS = (1, 5, 15, 30, 60)  # секунды между попытками
    _SEND_TIMEOUT = aiohttp.ClientTimeout(total=10)  # таймаут для POST /messages

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 300,
        max_retries: int | None = None,
    ) -> None:
        """
        :param base_url: Базовый URL API, например https://platform-api.max.ru
        :param token: Bearer-токен авторизации
        :param timeout: Таймаут одного long poll запроса в секундах (по умолчанию 5 минут)
        :param max_retries: Максимальное число повторных попыток подряд.
                            None — повторять бесконечно.
        """
        self._url = base_url.rstrip("/") + "/updates"
        self._headers = {"Authorization": token}
        self._poll_timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_retries = max_retries
        self._marker: int | None = None
        self._poll_session: aiohttp.ClientSession | None = None  # только GET /updates
        self._send_session: aiohttp.ClientSession | None = None  # только POST /messages
        self._closed = False

    # ------------------------------------------------------------------
    # Контекстный менеджер
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "LongPoll":
        await self._ensure_poll_session()
        await self._ensure_send_session()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    async def listen(self) -> AsyncIterator[Update]:
        """
        Бесконечный асинхронный генератор.
        Переподключается при сетевых ошибках с экспоненциальными задержками.
        """
        await self._ensure_poll_session()
        consecutive_errors = 0

        while not self._closed:
            try:
                async for update in self._poll_once():
                    consecutive_errors = 0
                    yield update

            except asyncio.CancelledError:
                logger.info("LongPoll: задача отменена, останавливаемся")
                return

            except (ClientError, ServerTimeoutError, asyncio.TimeoutError) as exc:
                consecutive_errors += 1
                delay = self._get_retry_delay(consecutive_errors)

                if (
                    self._max_retries is not None
                    and consecutive_errors > self._max_retries
                ):
                    logger.error(
                        "LongPoll: превышено максимальное число попыток (%d). Останавливаемся.",
                        self._max_retries,
                    )
                    raise

                logger.warning(
                    "LongPoll: сетевая ошибка [попытка %d]: %s. Повтор через %d сек.",
                    consecutive_errors,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                logger.exception("LongPoll: неожиданная ошибка: %s", exc)
                raise

    async def send_message(
        self,
        params: SendMessageParams,
        request: SendMessageRequest,
    ) -> None:
        """
        Отправить сообщение пользователю или в чат через Max Platform API.

        POST /messages?user_id=...  — личное сообщение
        POST /messages?chat_id=...  — сообщение в чат

        :param params: Query-параметры (получатель + disable_link_preview)
        :param request: Тело запроса (текст, вложения, форматирование и т.д.)
        :raises RuntimeError: если клиент не инициализирован через async with
        :raises aiohttp.ClientResponseError: при HTTP-ошибке от API
        :raises ValueError: если params или request не валидны

        Примеры:

        Личное сообщение пользователю:
            await lp.send_message(
                params=SendMessageParams(user_id=123),
                request=SendMessageRequest(text="Привет!"),
            )

        Сообщение в чат без превью ссылок:
            await lp.send_message(
                params=SendMessageParams(chat_id=456, disable_link_preview=True),
                request=SendMessageRequest(
                    text="Ссылка: https://example.com",
                    format="html",
                ),
            )

        Ответ на сообщение с кнопкой:
            await lp.send_message(
                params=SendMessageParams(user_id=123),
                request=SendMessageRequest(
                    text="Выберите действие",
                    link=MessageLink(type="reply", mid="msg-abc"),
                    attachments=[
                        InlineKeyboardAttachment(
                            payload=InlineKeyboardPayload(
                                buttons=[[LinkButton(text="Сайт", url="https://example.com")]]
                            )
                        )
                    ],
                ),
            )
        """
        await self._ensure_send_session()

        if self._send_session is None:
            raise RuntimeError(
                "Сессия не инициализирована. Используйте 'async with LongPoll(...)'"
            )

        url = self._url.replace("/updates", "/messages")

        logger.debug(
            "LongPoll.send_message: отправка (params=%s), текст=%r",
            params.to_query(),
            request.text,
        )

        async with self._send_session.post(
            url,
            params=params.to_query(),
            json=request.to_api_payload(),
        ) as resp:
            if resp.status == 403:
                logger.warning(
                    "LongPoll.send_message: нет доступа (403 Forbidden), params=%s. "
                    "Возможно, пользователь не запускал бота.",
                    params.to_query(),
                )
                return

            if resp.status == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning(
                    "LongPoll.send_message: rate limit (429), ждём %d сек.",
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                return

            resp.raise_for_status()

            logger.debug(
                "LongPoll.send_message: успешно отправлено (params=%s, status=%d)",
                params.to_query(),
                resp.status,
            )

    async def close(self) -> None:
        """Закрыть обе сессии и освободить ресурсы."""
        self._closed = True
        if self._poll_session and not self._poll_session.closed:
            await self._poll_session.close()
            logger.debug("LongPoll: poll-сессия закрыта")
        if self._send_session and not self._send_session.closed:
            await self._send_session.close()
            logger.debug("LongPoll: send-сессия закрыта")

    # ------------------------------------------------------------------
    # Внутренняя логика
    # ------------------------------------------------------------------

    async def _ensure_poll_session(self) -> None:
        if self._poll_session is None or self._poll_session.closed:
            self._poll_session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=self._poll_timeout,
            )
            logger.debug(
                "LongPoll: создана poll-сессия (timeout=%s)", self._poll_timeout
            )

    async def _ensure_send_session(self) -> None:
        if self._send_session is None or self._send_session.closed:
            self._send_session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=self._SEND_TIMEOUT,
            )
            logger.debug(
                "LongPoll: создана send-сессия (timeout=%s)", self._SEND_TIMEOUT
            )

    async def _poll_once(self) -> AsyncIterator[Update]:
        """Один запрос к /updates, возвращает обновления через yield."""
        params = {"marker": self._marker} if self._marker is not None else {}

        logger.debug("LongPoll: отправляем запрос (marker=%s)", self._marker)

        if self._poll_session is None:
            raise RuntimeError(
                "Сессия не инициализирована. Используйте 'async with LongPoll(...)'"
            )

        async with self._poll_session.get(self._url, params=params) as resp:
            resp.raise_for_status()
            raw = await resp.text()

        response = LongPollResponse.model_validate_json(raw)
        self._marker = response.marker

        logger.debug(
            "LongPoll: получено %d обновлений, новый marker=%s",
            len(response.updates),
            self._marker,
        )

        for update in response.updates:
            yield update

    def _get_retry_delay(self, attempt: int) -> int:
        return self._RETRY_DELAYS[min(attempt - 1, len(self._RETRY_DELAYS) - 1)]
