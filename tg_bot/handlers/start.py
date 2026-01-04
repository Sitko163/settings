from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from keyboards import menu_keyboard, admin_keyboard
import text
from decouple import config
from db_handler import db_class
from create_bot import bot

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: Message):
    db = db_class.PostgresHandler()
    uid = message.from_user.id
    if uid == int(config('TG_ADMIN')):
        await message.answer(text.adm_greet.format(name=message.from_user.full_name), reply_markup=admin_keyboard.admin_menu())
    else:
        query = "SELECT * FROM pilot WHERE tg_id = %s"
        res = db.fetchrow(query, (uid, ))
        if res:
            await message.answer(text.greet.format(name=message.from_user.full_name), reply_markup=menu_keyboard.menu)
        else:
            await message.answer(text.login_query.format(name=message.from_user.full_name))

            admin_chat_id = config("TG_ADMIN")
            tg_id = message.from_user.id
            username = message.from_user.full_name
            await bot.send_message(admin_chat_id, text.access_query.format(name=username, tg_id=tg_id),
                                   reply_markup=admin_keyboard.make_accept_keyboard(tg_id, username))


@start_router.message(F.text == "Меню")
@start_router.message(F.text == "Выйти в меню")
@start_router.message(F.text == "◀️ Выйти в меню")
async def menu(msg: Message):
    await msg.answer(text.menu, reply_markup=menu_keyboard.menu)