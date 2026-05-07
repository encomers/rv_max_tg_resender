# rv-max

Мост между [Max Platform](https://max.ru) и Telegram. Читает обновления из Max-канала через Long Poll API и пересылает сообщения (текст, фото, видео) в указанный Telegram-канал.

---

## Как это работает

```
Max Platform API  →  Long Poll  →  Parser  →  TelegramSender  →  Telegram-канал
```

1. `LongPoll` непрерывно слушает `/updates` Max API
2. `UpdateParser` конвертирует разметку Max (bold, italic, ссылки и т.д.) в HTML-теги Telegram
3. `TelegramSender` отправляет текст, одиночное фото/видео или media group через Bot API
4. Рекламные сообщения (с маркером `реклама` + `erid=` / `токен:`) автоматически пропускаются

---

## Требования

- Python 3.14+
- Telegram-бот с правами администратора в целевом канале
- Токен Max Platform API

---

## Установка

```bash
git clone https://github.com/your-org/rv-max.git
cd rv-max
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

---

## Конфигурация

Создайте файл `.env` в корне проекта:

```env
# Токен Max Platform (Bearer-токен)
MAX_TOKEN=Bearer your_max_token_here

# Базовый URL Max API (по умолчанию https://platform-api.max.ru)
MAX_BASE_URL=https://platform-api.max.ru

# Токен Telegram-бота (от @BotFather)
TG_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ID Telegram-канала (например -1001234567890)
TG_CHANNEL_ID=-1001234567890
```

> Получить `TG_CHANNEL_ID` можно, переслав любое сообщение из канала боту [@userinfobot](https://t.me/userinfobot).

---

## Запуск

```bash
python -m src.main
```

Или напрямую:

```bash
python main.py
```

---

## Docker

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "-m", "src.main"]
```

```bash
docker build -t rv-max .
docker run --env-file .env rv-max
```

---

## Структура проекта

```
rv-max/
├── src/
│   ├── models/
│   │   └── updates.py        # Pydantic-модели ответов Max API
│   └── services/
│       ├── interface.py      # Абстракции ILongPoll, IMessageSender
│       ├── max_reader.py     # Long Poll клиент (reader.py)
│       ├── message_parser.py # Парсер и конвертер разметки (parser.py)
│       └── message_sender.py # Отправка в Telegram (telegram_sender.py)
├── main.py                   # Точка входа
├── pyproject.toml
└── .env                      # Не коммитить!
```

---

## Поведение при ошибках

| Ситуация | Поведение |
|---|---|
| Сетевая ошибка Long Poll | Retry с задержкой 1 → 5 → 15 → 30 → 60 сек |
| Падение всего цикла | Переподключение с экспоненциальным backoff (2–60 сек) |
| Ошибка отправки в Telegram | Логируется, цикл продолжается |
| Рекламное сообщение | Пропускается автоматически |
| Пустое сообщение | Игнорируется |

---

## Поддерживаемые типы контента

**Текстовая разметка Max → Telegram HTML:**

| Max | Telegram |
|---|---|
| `strong` | `<b>` |
| `emphasized` | `<i>` |
| `underline` | `<u>` |
| `monospaced` | `<code>` |
| `strikethrough` | `<s>` |
| `link` | `<a href="...">` |

**Медиа:**
- Одиночное фото → `send_photo`
- Одиночное видео → `send_video`
- Несколько файлов → `send_media_group` (до 10 элементов)

---

## Зависимости

| Пакет | Назначение |
|---|---|
| `aiogram==2.15` | Telegram Bot API |
| `aiohttp>=3.13.5` | Async HTTP клиент (Long Poll + скачивание медиа) |
| `pydantic>=2.13.4` | Валидация и десериализация ответов API |
| `python-dotenv>=1.2.2` | Загрузка конфигурации из `.env` |

---

## Лицензия

MIT
