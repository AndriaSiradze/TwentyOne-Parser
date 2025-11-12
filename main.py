import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from langchain.chat_models import init_chat_model

from infrastructure.database.setup import create_engine, create_session_pool
from parser.broadcaster import Broadcaster
from parser.config import load_config
from parser.news_checker import NewsChecker
from parser.parser_main import NewsManager, setup_logging


async def main():
    config = load_config('.env')
    # Creating Session pool
    engine = create_engine(db=config.db)
    session_pool = create_session_pool(engine)
    # Initializing Bot
    bot = Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode='html'))
    # Setting Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.start()
    broadcaster = Broadcaster(
        bot,
        admins=(496069806,),
        redaction_group=config.tg_bot.redaction_id,
        scheduler=scheduler,
        free_group_id=config.tg_bot.free_group_id
    )
    news_check_llm = init_chat_model(
        model='gpt-4.1-nano-2025-04-14',
        model_provider='openai',
    )
    news_format_llm = init_chat_model(
        model='gpt-4o-mini-2024-07-18',
        model_provider='openai',
        temperature=0.5
    )
    news_translate_llm = init_chat_model(
        model='gpt-5-2025-08-07',
        model_provider='openai',
        temperature=0.2
    )

    news_checker = NewsChecker(news_check_llm, session_pool, broadcaster=broadcaster)

    parser = NewsManager(
        news_format_llm=news_format_llm,
        news_translate_llm=news_translate_llm,
        broadcaster=broadcaster,
        news_checker=news_checker,
        # driver=driver
    )
    driver = parser.setup_selenium()
    driver_path = driver
    # driver_path = "/usr/local/bin/chromedriver"
    await parser.posting_task(config, session_pool, driver_path=driver_path)


if __name__ == '__main__':
    setup_logging()
    asyncio.run(main())
