import asyncio
import logging
import os
import random
from typing import Optional

from dotenv import load_dotenv

from src.models.requests import SendMessageParams, SendMessageRequest
from src.models.updates import Update
from src.services.max_reader import LongPoll
from src.services.message_parser import UpdateParser
from src.services.message_sender import TelegramSender

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("MAX_BASE_URL", "https://platform-api.max.ru")
MAX_TOKEN = os.getenv("MAX_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHANNEL_ID = os.getenv("TG_CHANNEL_ID")
ACCEPTED_MAX_CHANNEL = os.getenv("ACCEPTED_MAX_CHANNEL")

MIN_RECONNECT_DELAY = 2
MAX_RECONNECT_DELAY = 60


def parse_channel_id(value: Optional[str]) -> int:
    if not value:
        raise ValueError("TG_CHANNEL_ID is not set")
    return int(value)


def should_skip_text(text: str) -> bool:
    lowered = text.lower()
    return "реклама" in lowered and ("токен:" in lowered or "erid=" in lowered)


async def handle_update(
    update: Update, parser: UpdateParser, telegram: TelegramSender
) -> None:
    try:
        print(update.model_dump_json(indent=4))
        message = getattr(update, "message", None)
        if message is None:
            return

        body = getattr(message, "body", None)
        text = getattr(body, "text", None)

        if not text or not text.strip():
            return

        if should_skip_text(text):
            logger.info("Skipped advertisement-like message")
            return

        parsed = parser.parse(update)
        if not parsed or parsed.text is None or not parsed.text.strip():
            return

        await telegram.send(
            text=parsed.text,
            image_urls=parsed.image_urls or [],
            video_urls=parsed.video_urls or [],
        )

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Failed to process update")


async def run_once() -> None:

    if not MAX_TOKEN:
        raise RuntimeError("MAX_TOKEN is not set")
    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN is not set")

    parser = UpdateParser()

    async with LongPoll(base_url=BASE_URL, token=MAX_TOKEN) as lp:
        async with TelegramSender(
            token=TG_TOKEN,
            channel_id=parse_channel_id(TG_CHANNEL_ID),
        ) as telegram:
            async for update in lp.listen():
                if (
                    ACCEPTED_MAX_CHANNEL is not None
                    and update.message is not None
                    and update.message.recipient.chat_type == "channel"
                    and str(update.message.recipient.chat_id) != ACCEPTED_MAX_CHANNEL
                ):
                    print(str(update.message.recipient.chat_id))
                    print(ACCEPTED_MAX_CHANNEL)
                    continue

                if (
                    update.message is not None
                    and update.message.recipient.chat_type in ["chat", "dialog"]
                ):
                    params = SendMessageParams(chat_id=update.message.recipient.chat_id)
                    send_message = SendMessageRequest(
                        text=update.model_dump_json(indent=4)
                    )
                    await lp.send_message(
                        params=params,
                        request=send_message,
                    )
                else:
                    await handle_update(update, parser, telegram)


async def main() -> None:
    if not MAX_TOKEN:
        raise RuntimeError("MAX_TOKEN is not set")
    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN is not set")
    if not TG_CHANNEL_ID:
        raise RuntimeError("TG_CHANNEL_ID is not set")

    delay = MIN_RECONNECT_DELAY

    while True:
        try:
            await run_once()
            delay = MIN_RECONNECT_DELAY
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Long-poll loop crashed; reconnecting in %.1f sec", delay)
            await asyncio.sleep(delay + random.uniform(0, 0.5))
            delay = min(delay * 2, MAX_RECONNECT_DELAY)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
