from sqlalchemy import select, insert

from infrastructure.database.models import Url
from infrastructure.database.repo.base import BaseRepo


class UrlsRepo(BaseRepo):
    async def get_all_urls(
            self,
    ) -> list[Url]:
        select_stmt = (
            select(Url)
        )
        result = await self.session.execute(select_stmt)

        return result.scalars().all()

    async def save_url(self, url: str, check: bool):
        insert_stmt = (
            insert(Url)
            .values(url=url,
                    check_news=check)
        )

        await self.session.execute(insert_stmt)
        await self.session.commit()
