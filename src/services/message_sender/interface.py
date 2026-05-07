from abc import ABC, abstractmethod


class IMessageSender(ABC):
    @abstractmethod
    async def send(
        self,
        text: str,
        image_urls: list[str] | None = None,
        video_urls: list[str] | None = None,
    ) -> None: ...
