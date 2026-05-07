from dataclasses import dataclass
from html import escape

from src.models.updates import MarkupElement, Update


@dataclass
class ParsedUpdate:
    text: str | None
    image_urls: list[str]
    video_urls: list[str]


class UpdateParser:
    """
    Парсит Update из Max API в структуру, готовую для отправки в Telegram.
    Конвертирует markup в HTML-теги Telegram.
    """

    _TAG_MAP: dict[str, tuple[str, str]] = {
        "strong": ("<b>", "</b>"),
        "emphasized": ("<i>", "</i>"),
        "underline": ("<u>", "</u>"),
        "monospaced": ("<code>", "</code>"),
        "strikethrough": ("<s>", "</s>"),
    }

    def parse(self, update: Update) -> ParsedUpdate:
        if update.message is None:
            return ParsedUpdate(text=None, image_urls=[], video_urls=[])

        body = update.message.body

        text = self._build_html(body.text, body.markup) if body.text else None

        image_urls: list[str] = []
        video_urls: list[str] = []

        for attachment in body.attachments or []:
            url = attachment.payload.url
            if url is None:
                continue
            if attachment.type == "image":
                image_urls.append(url)
            elif attachment.type == "video":
                video_urls.append(url)

        return ParsedUpdate(text=text, image_urls=image_urls, video_urls=video_urls)

    def _build_html(self, text: str, markup: list[MarkupElement] | None) -> str:
        if not markup:
            return escape(text)

        # Собираем события открытия/закрытия тегов по позициям символов
        # Каждое событие: (позиция, приоритет, тег)
        # Приоритет нужен чтобы закрывающие теги шли раньше открывающих на одной позиции
        events: list[tuple[int, int, str]] = []

        for mark in markup:
            start = mark.from_
            end = mark.from_ + mark.length

            if mark.type == "link" and mark.url:
                open_tag = f'<a href="{escape(mark.url)}">'
                close_tag = "</a>"
            elif mark.type in self._TAG_MAP:
                open_tag, close_tag = self._TAG_MAP[mark.type]
            else:
                continue

            events.append((start, 1, open_tag))  # 1 = открывающий (позже закрывающих)
            events.append((end, 0, close_tag))  # 0 = закрывающий (раньше открывающих)

        events.sort(key=lambda e: (e[0], e[1]))

        result: list[str] = []
        prev = 0

        for pos, _, tag in events:
            if pos > prev:
                result.append(escape(text[prev:pos]))
            result.append(tag)
            prev = pos

        if prev < len(text):
            result.append(escape(text[prev:]))

        return "".join(result)
