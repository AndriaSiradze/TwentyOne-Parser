import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class Broadcaster:
    def __init__(self, bot: Bot, admins: tuple, redaction_group: int, scheduler: AsyncIOScheduler, free_group_id: int):
        self.bot = bot
        self.admins = admins
        self.redaction_group = redaction_group
        self.scheduler = scheduler
        self.free_group_id = free_group_id

    async def send_to_free(self, translate_result, source):
        text = await self.build_response(translate_result, source)
        run_time = datetime.utcnow() + timedelta(minutes=1)

        self.scheduler.add_job(
            self.bot.send_message,
            trigger='date',
            args=[self.free_group_id, text],
            next_run_time=run_time
        )

    async def send_message_to_all_admins(self, msg):
        for admin in self.admins:
            await self.bot.send_message(admin, msg)

    @staticmethod
    async def _get_website_name(url: str) -> str:
        """
        Извлекает название сайта из URL.
        Пример: https://www.example.com/page -> example
        """
        match = re.search(r"https?://(?:www\.)?([^/.]+)", url)
        if match:
            return match.group(1)
        raise ValueError('Could not extract website name from URL')

    async def send_news_for_all_users(self, translate_result, source, users):
        text = await self.build_response(translate_result, source)
        for user in users:
            try:
                await self.bot.send_message(user, text)
            except TelegramForbiddenError as err:
                logging.error(f"{user} blocked the bot")
            except TelegramBadRequest as err:
                logging.error(f"{user} {err}")

    async def send_post_to_redaction(self, translate_result, source):
        logging.info('broadcasting')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅", callback_data="save"),
             InlineKeyboardButton(text="✏️", callback_data="edit"),
             InlineKeyboardButton(text="🗑", callback_data='delete')]
        ])

        text = await self.build_response(translate_result, source)
        message = await self.bot.send_message(self.redaction_group, text, reply_markup=keyboard,
                                              link_preview_options=LinkPreviewOptions(is_disabled=True))
        return message.message_id

    async def build_response(self, translate_result, source):
        tags_as_text = '\n'.join([f"#{tag}" for tag in translate_result.tags_ru])
        source_link = f"<a href='{source}'>{await self._get_website_name(source)}</a>"
        return f"{translate_result.title_ru}\n\n{translate_result.body_ru}\n\n{tags_as_text}\n\n{source_link}"
