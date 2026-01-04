import asyncio
from create_bot import bot, dp, scheduler
from handlers.start import start_router
from handlers.form_filling import form_router
from handlers.admin import admin_router
from handlers.data_changing import userdata_router

# from work_time.time_func import send_time_msg

async def main():
    # scheduler.add_job(send_time_msg, 'interval', seconds=10)
    # scheduler.start()
    #dp.message.middleware(logging_middleware.LogAllEventsMiddleware())
    #dp.callback_query.middleware(logging_middleware.LogAllEventsMiddleware())#
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(form_router)
    dp.include_router(userdata_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())