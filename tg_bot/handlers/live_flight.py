"""Старт/Стоп оперативных вылетов — логика в Django (общий проект)."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message
from decouple import config

from flights.utils.live_flight import (
    LIVE_FLIGHT_ACTION_START,
    LIVE_FLIGHT_ACTION_STOP,
    record_live_flight_event,
)

logger = logging.getLogger(__name__)

live_flight_router = Router()

LIVE_FLIGHT_CHAT_ID = int(config('TELEGRAM_LIVE_FLIGHT_CHAT_ID', default=-1003960872491))

CMD_START = 'Старт'
CMD_STOP = 'Стоп'


def process_live_flight_message(message: Message):
    text = (message.text or '').strip()
    if text == CMD_START:
        action = LIVE_FLIGHT_ACTION_START
    elif text == CMD_STOP:
        action = LIVE_FLIGHT_ACTION_STOP
    else:
        return

    result = record_live_flight_event(
        action=action,
        telegram_user_id=message.from_user.id,
        chat_id=message.chat.id,
        message_id=message.message_id,
    )
    if result.get('ok'):
        logger.info('%s: %s (tg_id=%s)', text, result.get('callname'), message.from_user.id)
    elif result.get('error') == 'pilot_not_linked':
        logger.warning('%s: tg_id=%s не привязан к пилоту', text, message.from_user.id)
    elif result.get('error') == 'no_active_flight':
        logger.info('%s: нет активного вылета (tg_id=%s)', text, message.from_user.id)
    else:
        logger.warning('%s: %s', text, result)


@live_flight_router.message(F.chat.id == LIVE_FLIGHT_CHAT_ID, F.text)
async def on_live_flight_group_message(message: Message):
    await asyncio.to_thread(process_live_flight_message, message)
