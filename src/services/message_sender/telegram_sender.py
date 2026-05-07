import logging
from io import BytesIO

import aiohttp
from aiogram import Bot  # type: ignore[import-untyped]
from aiogram.types import (  # type: ignore[import-untyped]
    InputFile,
    MediaGroup,
)

from .interface import IMessageSender

logger = logging.getLogger(__name__)


class TelegramSender(IMessageSender):
    def __init__(self, token: str, channel_id: int | str) -> None:
        self._bot = Bot(token=token, parse_mode="HTML")
        self._channel_id = channel_id
        self._http: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "TelegramSender":
        self._http = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def send(
        self,
        text: str,
        image_urls: list[str] | None = None,
        video_urls: list[str] | None = None,
    ) -> None:
        images = image_urls or []
        videos = video_urls or []
        media = images + videos

        try:
            if not media:
                await self._send_text(text)
            elif len(media) == 1:
                await self._send_single(text, images, videos)
            else:
                await self._send_media_group(text, images, videos)
        except Exception as exc:
            logger.exception("TelegramSender: ошибка при отправке: %s", exc)
            raise

    async def close(self) -> None:
        if self._http and not self._http.closed:
            await self._http.close()
        await self._bot.close()
        logger.debug("TelegramSender: сессии закрыты")

    async def _send_text(self, text: str) -> None:
        logger.debug("TelegramSender: отправка текста")
        await self._bot.send_message(
            chat_id=self._channel_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    async def _send_single(
        self, text: str, images: list[str], videos: list[str]
    ) -> None:
        if images:
            file = await self._download(images[0])
            logger.debug("TelegramSender: отправка одиночного фото")
            await self._bot.send_photo(
                chat_id=self._channel_id,
                photo=file,
                caption=text,
                parse_mode="HTML",
            )
        else:
            file = await self._download(videos[0])
            logger.debug("TelegramSender: отправка одиночного видео")
            await self._bot.send_video(
                chat_id=self._channel_id,
                video=file,
                caption=text,
                parse_mode="HTML",
            )

    async def _send_media_group(
        self, text: str, images: list[str], videos: list[str]
    ) -> None:
        logger.debug(
            "TelegramSender: отправка media group (%d фото, %d видео)",
            len(images),
            len(videos),
        )

        album = MediaGroup()

        for i, url in enumerate(images):
            file = await self._download(url)
            is_first = i == 0
            album.attach_photo(
                file,
                caption=text if is_first else None,  # type: ignore[call-arg]
                parse_mode="HTML",
            )  # type: ignore[call-arg]

        for i, url in enumerate(videos):
            file = await self._download(url)
            is_first = i == 0 and not images
            album.attach_video(
                file,
                caption=text if is_first else None,  # type: ignore[call-arg]
                parse_mode="HTML",
            )

        await self._bot.send_media_group(  # type: ignore[call-arg]
            chat_id=self._channel_id,
            media=album,  # type: ignore[call-arg]
        )

    async def _download(self, url: str) -> InputFile:
        if self._http is None:
            raise RuntimeError("Используйте 'async with TelegramSender(...)'")

        logger.debug("TelegramSender: скачиваем %s", url)
        async with self._http.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()

        filename = url.split("/")[-1].split("?")[0] or "file"
        return InputFile(BytesIO(data), filename=filename)
