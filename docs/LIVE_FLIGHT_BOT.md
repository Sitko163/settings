# Telegram-бот в составе проекта

Бот — часть репозитория `settings`, общая среда с Django:

- один `.env` (TOKEN, POSTGRES_*, REDIS_URL, TELEGRAM_LIVE_FLIGHT_CHAT_ID);
- одна PostgreSQL;
- запуск: `python manage.py run_telegram_bot`.

## Docker (всё вместе)

```bash
docker compose up -d --build
```

Сервисы: `api`, `tg-bot`, `webserver`, `database`, `redis`.

- **Веб:** http://localhost:8888  
- **Дашборд:** http://localhost:8888/dashboard/ (карта, погода, оповещения из [топика 2408](https://t.me/c/3960872491/2408))  
- **Бот:** контейнер `rubicon_tg_bot`, команда `run_telegram_bot`

Важно: не запускайте второй экземпляр бота с тем же `TOKEN` вне Docker (будет `TelegramConflictError`).

## Локально без Docker

```bash
cd rubicon_admin
pip install -r ../api/requirements.txt
python manage.py run_telegram_bot
```

Каталог `tg_bot` должен лежать рядом с `rubicon_admin`.

## Старт / Стоп

- Группа: `TELEGRAM_LIVE_FLIGHT_CHAT_ID=-1003960872491`
- Сообщения: только **`Старт`** и **`Стоп`**
- Пилот по `tg_id` в карточке `Pilot` (админка)

## Разработка

- Код бота: `tg_bot/` (монтируется в `/code/tg_bot`)
- Логика вылетов: `rubicon_admin/flights/utils/live_flight.py`
- API дашборда: `GET /api/live_dashboard/`
