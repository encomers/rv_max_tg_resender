import asyncio
import logging
from typing import AsyncIterator

import aiohttp
from aiohttp import ClientError, ServerTimeoutError

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
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_retries = max_retries
        self._marker: int | None = None
        self._session: aiohttp.ClientSession | None = None
        self._closed = False

    # ------------------------------------------------------------------
    # Контекстный менеджер
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "LongPoll":
        await self._ensure_session()
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
        await self._ensure_session()
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

    async def close(self) -> None:
        """Закрыть сессию и освободить ресурсы."""
        self._closed = True
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("LongPoll: сессия закрыта")

    # ------------------------------------------------------------------
    # Внутренняя логика
    # ------------------------------------------------------------------

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=self._timeout,
            )
            logger.debug("LongPoll: создана новая HTTP-сессия")

    async def _poll_once(self) -> AsyncIterator[Update]:
        """Один запрос к /updates, возвращает обновления через yield."""
        params = {"marker": self._marker} if self._marker is not None else {}

        logger.debug("LongPoll: отправляем запрос (marker=%s)", self._marker)

        if self._session is None:
            raise RuntimeError(
                "Сессия не инициализирована. Используйте 'async with LongPoll(...)'"
            )

        async with self._session.get(self._url, params=params) as resp:
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
