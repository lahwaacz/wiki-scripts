# TODO:
# - intel.com and its subdomains are returning false 404

import asyncio
import logging
from types import ModuleType
from typing import Any, Iterable

import sqlalchemy as sa
import sqlalchemy.orm
from sqlalchemy.ext.asyncio import async_sessionmaker

try:
    tqdm: ModuleType | None
    import tqdm
    import tqdm.contrib.logging
except ImportError:
    tqdm = None

from ws.db.database import Database

from .URLStatusChecker import Domain, LinkCheck, URLStatusChecker

__all__ = ["ExtlinkStatusChecker"]

logger = logging.getLogger(__name__)


class ExtlinkStatusChecker(URLStatusChecker):
    def __init__(self, db: Database, **kwargs: Any):
        super().__init__(**kwargs)

        self.db = db

        # initialize SQLAlchemy ORM
        mapper_registry = sqlalchemy.orm.registry()
        mapper_registry.map_imperatively(
            Domain,
            self.db.ws_domain,
        )
        mapper_registry.map_imperatively(
            LinkCheck,
            self.db.ws_url_check,
            properties={
                "domain": sqlalchemy.orm.relationship(
                    Domain, backref="url_checks", lazy="joined"
                )
            },
        )
        self.session = sqlalchemy.orm.sessionmaker(self.db.engine)
        self.async_session = async_sessionmaker(
            self.db.async_engine, expire_on_commit=False
        )

        # optional tqdm progressbar
        self.progress = None

    def transfer_urls_from_parser_cache(self):
        """Transfers URLs from the MediaWiki-like ``externallinks`` table
        to the wiki-scripts' ``ws_url_check`` and ``ws_domain`` tables.
        """
        el = self.db.externallinks
        ws_dom = self.db.ws_domain
        ws_url = self.db.ws_url_check

        with self.db.engine.begin() as conn:
            urls = {}
            sel = (
                sa.select(el.c.el_to)
                .select_from(el)
                .distinct()
                .order_by(el.c.el_to.asc())
            )
            for row in conn.execute(sel):
                # note that URLs are stored as URL-decoded strings so they may seem weird/invalid at first
                url = row[0]
                if self.is_checkable_url(url) is True:
                    url = self.normalize_url(url)
                    urls[str(url)] = self.get_domain(url)

            # insert all domains first
            logger.info("Inserting new domains to the ws_domain table...")
            ins = sa.dialects.postgresql.insert(ws_dom).on_conflict_do_nothing()
            conn.execute(ins, [{"name": domain} for domain in urls.values()])

            # insert all URLs
            logger.info("Inserting new URLs to the ws_url_check table...")
            ins = sa.dialects.postgresql.insert(ws_url).on_conflict_do_nothing()
            conn.execute(
                ins,
                [{"domain_name": domain, "url": url} for url, domain in urls.items()],
            )

    async def lock_domain_and_check_link(
        self,
        semaphore: asyncio.Semaphore,
        domain_locks: dict[str, asyncio.Lock],
        link: LinkCheck,
    ) -> None:
        lock = domain_locks[link.domain_name]
        async with lock:
            async with semaphore:
                # work with each link in a separate async session
                async with self.async_session() as session:
                    session.add(link)
                    await self.check_link(link)
                    await session.commit()
                    if self.progress is not None:
                        self.progress.update(1)

    @staticmethod
    def _get_domain_locks(domains: Iterable[Domain]) -> dict[str, asyncio.Lock]:
        locks = {}
        # create separate lock for each domain
        for domain in domains:
            locks[domain.name] = asyncio.Lock()

        # merge locks for all *.sourceforge.net subdomains
        # (otherwise we often get HTTP status 429 Too Many Requests)
        common_lock = locks.setdefault("sourceforge.net", asyncio.Lock())
        for domain_name in locks.keys():
            if domain_name.endswith(".sourceforge.net"):
                locks[domain_name] = common_lock

        # merge locks for all domains in the StackExchange network
        # (otherwise we often get HTTP status 429 Too Many Requests)
        # the domains list is from https://meta.stackexchange.com/a/81383
        se_domains = {
            "askubuntu.com",
            "mathoverflow.net",
            "serverfault.com",
            "stackoverflow.com",
            "stackexchange.com",
            "stackapps.com",
            "superuser.com",
        }
        common_lock = asyncio.Lock()
        for domain_name in locks.keys():
            for se_domain in se_domains:
                if domain_name == se_domain or domain_name.endswith("." + se_domain):
                    locks[domain_name] = common_lock

        return locks

    def check(self, select_stmt):
        with self.session.begin() as session:
            # create domain locks
            domains = session.scalars(sa.select(Domain))
            locks = self._get_domain_locks(domains)

            # obtain the link objects
            links = list(session.scalars(select_stmt))

            # detach all objects from the global ORM session
            session.expunge_all()

        logger.info(
            f"Checking the status of {len(links)} URLs (success is logged with DEBUG level)..."
        )

        # use a semaphore to limit the number of "active workers" in the task group
        semaphore = asyncio.Semaphore(100)

        async def async_exec():
            async with asyncio.TaskGroup() as tg:
                for link in links:
                    tg.create_task(
                        self.lock_domain_and_check_link(semaphore, locks, link)
                    )

        if tqdm is not None:
            # initialize tqdm progressbar
            self.progress = tqdm.tqdm(total=len(links))
            with tqdm.contrib.logging.logging_redirect_tqdm():
                asyncio.run(async_exec())
            self.progress.close()
        else:
            asyncio.run(async_exec())
