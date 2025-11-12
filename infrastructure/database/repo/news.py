from collections.abc import Iterable
from datetime import timedelta, datetime

from sqlalchemy import select, Sequence, func, update, delete
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.models.urls import Tag, Termin, News, RelevanceCheckResult, RedactionMessage
from infrastructure.database.repo.base import BaseRepo


class NewsRepo(BaseRepo):
    async def get_all_news(self) -> Iterable[News]:
        insert_stmt = (
            select(News)
        )
        result = await self.session.execute(insert_stmt)

        return result.scalars().all()

    async def save_news(self, title, body, title_ru, body_ru, source, source_text, slug):
        insert_stmt = (
            insert(News)
            .values(title=title,
                    body=body,
                    title_ru=title_ru,
                    body_ru=body_ru,
                    source_text=source_text,
                    source=source,
                    slug=slug
                    )
            .returning(News)
        )
        res = await self.session.execute(insert_stmt)
        await self.session.commit()
        return res.scalar_one()

    async def save_news_tag(self, tag_name: str, news_id, tag_name_ru: str):
        insert_stmt = (
            insert(Tag)
            .values(name=tag_name, news_id=news_id, name_ru=tag_name_ru)
        )
        await self.session.execute(insert_stmt)
        await self.session.commit()

    async def delete_tag_by_name_ru(self, tag_name: str, news_id):
        stmt = (
            delete(
                Tag
            )
            .where(
                Tag.news_id == news_id,
                Tag.name_ru == tag_name
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_terminology(self) -> list[Termin]:
        select_stmt = (
            select(Termin)
        )

        res = await self.session.execute(select_stmt)
        return res.scalars().all()

    async def get_latest_news(self, days=1) -> Sequence[News]:
        now = datetime.utcnow()
        last_days = now - timedelta(days=days)

        insert_stmt = (
            select(News)
            .where(News.created_at >= last_days)
        )
        result = await self.session.execute(insert_stmt)

        return result.scalars().all()

    async def save_check_result(self, reason: str, news_id: int):
        insrt_stmt = (
            insert(
                RelevanceCheckResult
            )
            .values(
                reason=reason,
                news_id=news_id,
            )
        )
        await self.session.execute(insrt_stmt)
        await self.session.commit()

    async def save_redaction_message(self, redaction_message_id, news_id):
        insrt_stmt = (
            insert(RedactionMessage)
            .values(
                message_id=redaction_message_id,
                news_id=news_id
            )
        )
        await self.session.execute(insrt_stmt)
        await self.session.commit()

    async def get_news_by_message_id(self, message_id):
        select_stmt = (
            select(
                News.news_id,
                News.title_ru,
                News.body_ru,
                func.array_agg(Tag.name_ru).label("tags"),
                News.source,
            )
            .join(
                News.messages
            )
            .join(
                Tag, Tag.news_id == News.news_id
            )
            .where(RedactionMessage.message_id == message_id)
            .group_by(News.news_id)
        )

        res = await self.session.execute(select_stmt)
        return res.all()

    async def approve_news(self, news_id):
        values = {
            'status': 'APPROVED',
        }
        updt_stmt = (
            update(
                News
            )
            .where(
                News.news_id == news_id
            )
            .values(
                values
            )
        )
        await self.session.execute(updt_stmt)
        await self.session.commit()

    async def decline_news(self, news_id):
        values = {'status': 'DECLINED'}

        updt_stmt = (
            update(
                News
            )
            .where(
                News.news_id == news_id
            )
            .values(
                values
            )

        )
        await self.session.execute(updt_stmt)
        await self.session.commit()

    async def set_new_body_ru(self, news_id, body_ru):
        updt_stmt = (
            update(
                News
            )
            .where(
                News.news_id == news_id
            )
            .values(
                body_ru=body_ru
            )
        )
        await self.session.execute(updt_stmt)
        await self.session.commit()

    async def update_title(self, title, news_id):
        updt_stmt = (
            update(
                News
            )
            .where(
                News.news_id == news_id
            )
            .values(
                title=title
            )
        )
        await self.session.execute(updt_stmt)
        await self.session.commit()
