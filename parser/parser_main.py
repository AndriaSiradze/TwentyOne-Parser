import asyncio
import logging
import re
import uuid
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Union

import betterlogging as bl
import feedparser
from langchain.chat_models.base import _ConfigurableModel
from langchain_community.document_loaders import SeleniumURLLoader, PlaywrightURLLoader
from langchain_core.language_models import BaseChatModel
from requests.models import ReadTimeoutError
from selenium import webdriver
from selenium.common import SessionNotCreatedException, NoSuchDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from infrastructure.database.repo.requests import RequestsRepo
from infrastructure.database.setup import create_engine, create_session_pool
from parser.broadcaster import Broadcaster
from parser.news_checker import NewsChecker
from parser.prompts import TRANSLATE_PROMPT, llm_output_parser, SUMMARIZE_PROMPT, llm_ru_output_parser

CheckResult = namedtuple('CheckResult', ['status', 'save'])


def setup_logging():
    """
    Set up logging configuration for the application.

    This method initializes the logging configuration for the application.
    It sets the log level to INFO and configures a basic colorized log for
    output. The log format includes the filename, line number, log level,
    timestamp, logger name, and log message.

    Returns:
        None

    Example usage:
        setup_logging()
    """
    log_level = logging.INFO
    bl.basic_colorized_config(level=log_level)

    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot")


@dataclass
class ParseResult:
    """dataclass to store Response From Summarization Chain"""
    title: str
    body: str
    tags: list[str]
    source_text: str


@dataclass
class TranslateRuResult(ParseResult):
    """dataclass to store Response From Translation Chain and Summartization"""
    title_ru: str
    body_ru: str
    tags_ru: list[str]

    @staticmethod
    def from_invoke(summarization_chain, translation_chain, source_text):
        return TranslateRuResult(
            **summarization_chain, **translation_chain, source_text=source_text
        )

    async def save_to_db(self, session_pool, source: str, base_title, reason: str, redaction_id):
        slug = f"{'-'.join([n.lower() for n in base_title.split(' ')])}" + f"{datetime.now()}"
        async with session_pool() as session:
            repo = RequestsRepo(session)
            news = await repo.news.save_news(
                title=base_title,
                body=self.body,
                title_ru=self.title_ru,
                body_ru=self.body_ru,
                source=source,
                source_text=self.source_text,
                slug=slug
            )
            for tag, tag_ru in zip(self.tags, self.tags_ru):
                await repo.news.save_news_tag(
                    tag_name=tag,
                    tag_name_ru=tag_ru,
                    news_id=news.news_id
                )
            await repo.news.save_check_result(news_id=news.news_id,
                                              reason=reason, )
            await repo.news.save_redaction_message(
                redaction_id,
                news.news_id
            )

        return news


def make_chrome_options():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-popup-blocking")
    return opts


class NewsManager:
    def __init__(self, news_format_llm: Union[BaseChatModel, _ConfigurableModel],
                 news_translate_llm: Union[BaseChatModel, _ConfigurableModel],
                 broadcaster: Broadcaster, news_checker: NewsChecker):

        self.news_format_llm = news_format_llm
        self.news_translate_llm = news_translate_llm
        self.broadcaster = broadcaster
        self.checker = news_checker
        # self.driver = driver
        # self.news_api_client = NewsApiClient(api_key='fd6b125bfa7147e89b1e07ed1e7de02a')

    @staticmethod
    async def get_slug(title):
        pass

    @staticmethod
    def setup_selenium():
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid detection
        chrome_options.add_argument("--disable-popup-blocking")  # Allow popups (sometimes needed)
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        return ChromeDriverManager().install()

    async def summarize_and_translate(self, raw_article, terms):
        """Making calls to llm to Summarize and translate article
        :return dict with title body title_ru, body_ru, tags, tags_ru"""
        summarize_chain = SUMMARIZE_PROMPT | self.news_format_llm | llm_output_parser
        translate_chain = TRANSLATE_PROMPT | self.news_translate_llm | llm_ru_output_parser

        sum_res = await summarize_chain.ainvoke(
            {'context': raw_article}
        )
        translation_res = await translate_chain.ainvoke(
            {
                'context': f"<b>{sum_res['title']}</b>\n{sum_res['body']}\n\n {sum_res['tags']}",
                'terms': f"{terms}"
            }
        )
        logging.info(sum_res)
        logging.info(translation_res)

        return TranslateRuResult.from_invoke(
            sum_res, translation_res, source_text=raw_article
        )

    async def posting_task(self, config, session_pool,driver_path):
        """
        Posting Flow
        itterating through each feed
        if article passing the checks
        proccedes article through llm
        """
        checked_entries = set()

        while True:
            logging.info('start iteration')
            async with session_pool() as session:
                # Getting All necessary data for itterating
                repo: RequestsRepo = RequestsRepo(session)
                urls_raw = await repo.urls.get_all_urls()
                terms = [f"{term.original} : {term.translation}" for term in
                         await repo.news.get_terminology()]
            # get_all_feeds = {url_obj:feedparser.parse(url_obj.url)}
            for url_obj in urls_raw:  # Processing urls for parse for database
                logging.info(f'Processing url {url_obj.url}')
                if url_obj.type_of_feed == 'rss':
                    feed = feedparser.parse(url_obj.url)
                    for entry in feed.entries[::-1]:  # Processing through feeds
                        if entry.link in checked_entries:
                            logging.info(f"link in cache")
                            continue
                        loader = SeleniumURLLoader(
                            urls=[entry.link],
                            headless=True,
                            arguments=[
                                "--no-sandbox",
                                "--disable-dev-shm-usage",
                                "--disable-gpu",
                                "--disable-blink-features=AutomationControlled",
                                "--disable-popup-blocking",
                                "--remote-debugging-port=0",  # avoids port collisions
                            ],
                            executable_path=driver_path
                        )
                        try:
                            docs = await loader.aload()
                            raw_article = ' '.join([content.page_content for content in docs])
                            title = docs[0].metadata['title']
                            source = docs[0].metadata['source']

                            match = re.match(r"^(.*?)\?utm_source", source)
                            if match:
                                source = match.group(1)

                            date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        except IndexError as err:
                            await self.broadcaster.send_message_to_all_admins(
                                f"error while getting article {entry.link} no data returned")
                            continue
                        except SessionNotCreatedException as err:
                            logging.error(err)
                            await self.broadcaster.send_message_to_all_admins(
                                f"error while getting article {entry.link} session not created")
                            continue
                        except ReadTimeoutError as err:
                            logging.info(err.args)
                            logging.error(err)
                            await self.broadcaster.send_message_to_all_admins(
                                f"Read timeout error")
                            continue
                        finally:
                            try:
                                loader._get_driver().quit()
                            except NoSuchDriverException as err:
                                logging.error(err)
                                await self.broadcaster.send_message_to_all_admins(
                                    f"unable obtain driver")
                                continue
                        check_entry = await self.checker.check(
                            title, source, raw_article, date
                        )
                        logging.info('checking entry')
                        if check_entry.failed:
                            checked_entries.add(entry.link)
                            continue  # If check is failed
                        try:
                            res = await self.summarize_and_translate(raw_article, terms)
                        except TypeError as err:
                            logging.error(err)
                            await self.broadcaster.send_message_to_all_admins(
                                f"Unable Tu summarize and translate err {err}")
                            continue
                        logging.info('sending to redaction')
                        redaction_message = await self.broadcaster.send_post_to_redaction(res, source)

                        news = await res.save_to_db(
                            session_pool=session_pool,
                            source=source,
                            base_title=title,
                            reason=check_entry.extra,
                            redaction_id=redaction_message
                        )
                        checked_entries.add(entry.link)
            logging.info('sleep 1 minute')
            await asyncio.sleep(120)
#
#
# async def main():
#     setup_logging()
#     logging.info('start')
#     config = load_config("../.env")
#     engine = create_engine(db=config.db)
#     session_pool = create_session_pool(engine)
#
#     # parser = AsyncParser(config.misc.ai_api_token, session_pool=session_pool, tg_admin=TgAdmin(
#     #     bot=
#     # ))
#
#     # await parser.process_urls()
#
