from abc import ABC, abstractmethod
from typing import AsyncIterator

from src.models.updates import Update


class ILongPoll(ABC):
    @abstractmethod
    def listen(self) -> AsyncIterator[Update]:
        """Бесконечный асинхронный генератор обновлений."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Освободить ресурсы."""
        ...
