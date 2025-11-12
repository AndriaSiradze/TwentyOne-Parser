import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Union

from langchain.chat_models.base import _ConfigurableModel
from langchain_core.language_models import BaseChatModel
from sqlalchemy.exc import IntegrityError

from infrastructure.database.repo.requests import RequestsRepo
from parser.broadcaster import Broadcaster
from parser.prompts import DUPLICATES_CHECK_PROMPT, llm_duplicates_parser, RELEVANCE_CHECK_PROMPT, llm_relevance_parser


class NewsFailReason:
    """Class to store AsyncParser._check_entry values """
    date: str = 'date'
    not_related: str = 'not related'
    duplicate: str = 'duplicate'
    exists: str = 'exists'
    none: str = 'none'


@dataclass
class CheckEntryResult:
    """Result of AsyncParser._check_entry """
    failed: bool
    reason: str = NewsFailReason.none
    extra: str = None


class NewsChecker:
    def __init__(self, llm, session_pool, broadcaster: Broadcaster):
        self.llm: Union[BaseChatModel, _ConfigurableModel] = llm
        self.session_pool = session_pool
        self.broadcaster = broadcaster

    async def check_relevance(self, article):
        logging.info(self.check_relevance.__name__)
        """
        Check if the news is related to Bitcoin.
        """
        relevance_check_chain = RELEVANCE_CHECK_PROMPT | self.llm | llm_relevance_parser
        try:
            relevance_check = await relevance_check_chain.ainvoke({'context': article})
            logging.info(relevance_check)
            relevant, reason = relevance_check.values()
            return relevant, reason
        except Exception as e:
            logging.error(f"Error checking news title '': {e}")
            return False

    async def check_duplicates(self, title):
        """Checks if similar titles was posted in last 24 hours"""
        logging.info('check duplicates')
        duplicates_chain = DUPLICATES_CHECK_PROMPT | self.llm | llm_duplicates_parser
        async with self.session_pool() as session:
            repo = RequestsRepo(session)
            last_titles = [news.title for news in await repo.news.get_latest_news()]

        result = (await duplicates_chain.ainvoke(
            {'title': title,
             'all_titles': last_titles}
        ))['result'].lower()
        return True if result == 'no' else False

    @staticmethod
    async def _check_for_date(date: datetime):
        """
        Check if the entry is older than 1 day based on its published date.
        :param entry:
        :return: True if the entry is recent (within 1 day), False otherwise.
        """
        logging.info(date)
        now = datetime.now(timezone.utc)
        time_diff = now - date

        # Skip if older than 1 day
        if time_diff > timedelta(days=1):
            hours_ago = time_diff.total_seconds() // 3600
            return False
        return True

    async def check(self, title, source, raw_article, date) -> CheckEntryResult:
        async with self.session_pool() as session:
            repo = RequestsRepo(session)
            last_news = [news.title for news in await repo.news.get_latest_news(days=3)]
            logging.info(last_news)
        if not await self._check_for_date(date):
            logging.info('date check failed')
            result = CheckEntryResult(failed=True,
                                      reason=NewsFailReason.date)
        elif title in last_news:
            logging.info('title exists in all titles')
            result = CheckEntryResult(failed=True,
                                      reason=NewsFailReason.exists)

        elif not await self.check_duplicates(title):
            """Ai Found duplicate"""
            result = CheckEntryResult(failed=True,
                                      reason=NewsFailReason.not_related)



        else:
            relevance, reason = await self.check_relevance(raw_article)
            logging.info(relevance)
            if relevance is False:
                result = CheckEntryResult(failed=True,
                                          reason=NewsFailReason.not_related,
                                          extra=reason)
            else:
                result = CheckEntryResult(failed=False,
                                          extra=reason)

        if result.reason in (NewsFailReason.not_related,
                             NewsFailReason.duplicate) and result.failed:
            slug = '-'.join([n.lower() for n in title.split(' ')])
            # Saving Title so it will fail on checking title in all titles
            try:
                async with self.session_pool() as session:
                    repo: RequestsRepo = RequestsRepo(session)

                    news = await repo.news.save_news(title=title, body='failed', source=source, title_ru='failed',
                                                     body_ru='failed', source_text=raw_article, slug=slug)
                    await repo.news.save_check_result(
                        reason=result.extra if result.extra else 'dublicate',
                        news_id=news.news_id,
                    )
            except IntegrityError as err:
                async with self.session_pool() as session:
                    repo: RequestsRepo = RequestsRepo(session)
                    logging.error(err)
                    slug = f"{slug}{datetime.now()}"
                    await self.broadcaster.send_message_to_all_admins(
                        f'ingerity error on news '
                    )
                    news = await repo.news.save_news(title=title, body='failed', source=source, title_ru='failed',
                                                     body_ru='failed', source_text=raw_article, slug=slug)
                    await repo.news.save_check_result(
                        reason=result.extra if result.extra else 'dublicate',
                        news_id=news.news_id,
                    )

        return result
