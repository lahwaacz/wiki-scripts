#! /usr/bin/env python3

# TODO:
# - intel.com and its subdomains are returning false 404

import asyncio
import datetime
import ipaddress
import logging
import ssl
from functools import lru_cache

import httpx
import sqlalchemy as sa
import sqlalchemy.orm
from sqlalchemy.ext.asyncio import async_sessionmaker

try:
    import tqdm
    import tqdm.contrib.logging
except ImportError:
    tqdm = None

try:
    import truststore
except ImportError:
    truststore = None

__all__ = ["ExtlinkStatusChecker", "Domain", "LinkCheck"]

logger = logging.getLogger(__name__)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARN)


# SQLAlchemy ORM with imperative mapping
# https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#imperative-mapping
class Domain:
    def __repr__(self):
        return f'Domain("{self.name},{self.last_check},{self.resolved},{self.server},{self.ssl_error}")'

class LinkCheck:
    def __repr__(self):
        return f"LinkCheck({self.url},{self.last_check},{self.check_duration},{self.http_status},{self.text_status},{self.result})"


# list of reserved IPv4 blocks: https://en.wikipedia.org/wiki/Reserved_IP_addresses
ipv4_reserved_networks = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("233.252.0.0/24"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
]

domains_with_ignored_status = {
    "aur.archlinux.org": {401},  # for private user account profiles
    "bbs.archlinux.org": {403, 404},  # 403 for user profiles and 404 for pages that require login
    "crates.io": {404},  # returns 404 to the script but 200 in web browser
}

class ExtlinkStatusChecker:
    def __init__(self, db, *, timeout=60, max_retries=3,
                 max_connections=100, keepalive_expiry=60):
        self.db = db

        # initialize SQLAlchemy ORM
        mapper_registry = sqlalchemy.orm.registry()
        mapper_registry.map_imperatively(
                Domain,
                db.ws_domain,
            )
        mapper_registry.map_imperatively(
                LinkCheck,
                db.ws_url_check,
                properties={
                    "domain": sqlalchemy.orm.relationship(Domain, backref="url_checks", lazy="joined")
                }
            )
        self.session = sqlalchemy.orm.sessionmaker(self.db.engine)
        self.async_session = async_sessionmaker(self.db.async_engine, expire_on_commit=False)

        # httpx client parameters
        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=None,  # always allow keep-alive
            keepalive_expiry=keepalive_expiry,
        )
        timeout = httpx.Timeout(timeout, pool=None)  # disable timeout for waiting for a connection from the pool
        headers = {
            # fake user agent to bypass servers responding differently or not at all to non-browser user agents
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
            # github.com always returns 404 without the Accept header
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
        }

        # create an SSL context to disallow TLS1.0 and TLS1.1, allow only TLS1.2
        # (and newer if supported by the used openssl version)
        if truststore is not None:
            # use the system certificate store if available via truststore
            ssl_context: ssl.SSLContext = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

        # initialize the HTTPX client
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self.client = httpx.AsyncClient(transport=transport, verify=ssl_context, headers=headers, timeout=timeout, limits=limits)

        # optional tqdm progressbar
        self.progress = None

    def transfer_urls_from_parser_cache(self):
        """ Transfers URLs from the MediaWiki-like ``externallinks`` table
            to the wiki-scripts' ``ws_url_check`` and ``ws_domain`` tables.
        """
        el = self.db.externallinks
        ws_dom = self.db.ws_domain
        ws_url = self.db.ws_url_check

        with self.db.engine.begin() as conn:
            urls = {}
            sel = sa.select(el.c.el_to).select_from(el).distinct().order_by(el.c.el_to.asc())
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
            conn.execute(ins, [{"domain_name": domain, "url": url} for url, domain in urls.items()])

    @staticmethod
    def is_checkable_url(url: str, *, allow_schemes=None):
        """ Returns ``True`` if the URL can be checked or ``False``.
        """
        if allow_schemes is None:
            allow_schemes = ["http", "https"]

        try:
            # try to parse the URL - fails e.g. if port is not a number
            # reference: https://www.python-httpx.org/api/#url
            url = httpx.URL(url)
        except httpx.InvalidURL:
            logger.debug(f"skipped invalid URL: {url}")
            return False

        # skip unsupported schemes
        if url.scheme not in allow_schemes:
            logger.debug(f"skipped URL with unsupported scheme: {url}")
            return False
        # skip URLs with empty host, e.g. "http://" or "http://git@" or "http:///var/run"
        # (partial workaround for https://github.com/earwig/mwparserfromhell/issues/196 )
        if not url.host:
            logger.debug(f"skipped URL with empty host: {url}")
            return False
        # skip URLs with auth info (e.g. http://login.worker:PWD@api.bitcoin.cz:8332)
        if url.userinfo:
            logger.debug(f"skipped URL with authentication credentials: {url}")
            return False
        # skip links with top-level domains only
        # (in practice they would be resolved relative to the local domain, on the wiki they are used
        # mostly as a pseudo-variable like http://server/path or http://mydomain/path)
        if "." not in url.host:
            logger.debug(f"skipped URL with only top-level domain host: {url}")
            return False
        # skip links to invalid/blacklisted domains
        if (url.host == "pi.hole"   # pi-hole configuration involves setting pi.hole in /etc/hosts
            or url.host == "ui.reclaim"  # GNUnet - the domains works only with a browser extension
            or url.host.endswith(".onion")  # Tor
            ):
            logger.debug(f"skipped URL with invalid/blacklisted domain host: {url}")
            return False
        # skip links to localhost
        if url.host == "localhost" or url.host.endswith(".localhost"):
            logger.debug(f"skipped URL to localhost: {url}")
            return False
        # skip links to reserved IP addresses
        try:
            addr = ipaddress.ip_address(url.host)
            for network in ipv4_reserved_networks:
                if addr in network:
                    logger.debug(f"skipped URL to IP address from reserved network: {url}")
                    return False
        except ValueError:
            pass

        return True

    @staticmethod
    def normalize_url(url: str):
        url = httpx.URL(url)

        # drop the fragment from the URL (to optimize caching)
        if url.fragment:
            url = httpx.URL(str(url).rsplit("#", maxsplit=1)[0])

        return url

    @staticmethod
    def get_domain(url: httpx.URL | str):
        if not isinstance(url, httpx.URL):
            url = httpx.URL(url)

        # httpx decodes punycodes for IDNs in .host, .raw_host is the original as bytes
        return url.raw_host.decode("utf-8")

    @staticmethod
    @lru_cache(maxsize=1024)
    def check_url_sync(url: httpx.URL | str, *, follow_redirects=True):
        """ Simplified and synchronous variant of ``check_url`` intended for other checksers like ExtlinkReplacements
        """
        if not isinstance(url, httpx.URL):
            url = httpx.URL(url)

        try:
            # We need to use GET requests instead of HEAD, because many servers just return 404
            # (or do not reply at all) to HEAD requests. Instead, we skip the downloading of the
            # response body content by using ``stream`` interface.
            with httpx.stream("GET", url, follow_redirects=follow_redirects) as response:
                # nothing to do here, but using the context manager ensures that the response is
                # always properly closed
                pass
        # FIXME: workaround for https://github.com/encode/httpx/discussions/2682#discussioncomment-5746317
        except ssl.SSLError as e:
            if "unable to get local issuer certificate" in str(e):
                # FIXME: this is a problem of the SSL library used by Python
                logger.warning(f"possible SSL error (unable to get local issuer certificate) for URL {url}")
                return
            else:
                logger.error(f"SSL error ({e}) for URL {url}")
                return False
        except httpx.ConnectError as e:
            if str(e).startswith("[SSL:"):
                if "unable to get local issuer certificate" in str(e):
                    # FIXME: this is a problem of the SSL library used by Python
                    logger.warning(f"possible SSL error (unable to get local issuer certificate) for URL {url}")
                    return
                else:
                    logger.error(f"SSL error ({e}) for URL {url}")
                    return False
            if "no address associated with hostname" in str(e).lower() \
                    or "name or service not known" in str(e).lower():
                logger.error(f"domain name could not be resolved for URL {url}")
                return False
            # other connection error - indeterminate
            logger.warning(f"connection error for URL {url}")
            return
        except httpx.TooManyRedirects as e:
            logger.error(f"TooManyRedirects error ({e}) for URL {url}")
            return False
        # it seems that httpx does not capture all exceptions, e.g. anyio.EndOfStream
        #except httpx.RequestError as e:
        except Exception as e:
            # e.g. ReadTimeout has no message in the async version,
            # see https://github.com/encode/httpx/discussions/2681
            msg = str(e)
            if not msg:
                msg = type(e)
            # base class exception - indeterminate
            logger.error(f"URL {url} could not be checked due to {msg}")
            return

        # check special domains
        if response.status_code in domains_with_ignored_status.get(url.host, []):
            logger.warning(f"status code {response.status_code} for URL {url}")
            return

        logger.debug(f"status code {response.status_code} for URL {url}")
        return response.status_code >= 200 and response.status_code < 300

    async def check_url(self, domain: Domain, link: LinkCheck, url: httpx.URL, *, follow_redirects=True):
        # reset domain attributes
        domain.last_check = link.last_check
        domain.resolved = None
        domain.ssl_error = None

        history = []

        try:
            # We need to follow redirects with a manual loop, because they may lead to other
            # domains and we need to handle their status separately. httpx does not allow to
            # get response.history after an exception.
            next_url = url
            while next_url is not None and len(history) <= self.client.max_redirects:
                history.append(next_url)
                # We need to use GET requests instead of HEAD, because many servers just return 404
                # (or do not reply at all) to HEAD requests. Instead, we skip the downloading of the
                # response body content by using ``stream`` interface.
                async with self.client.stream("GET", next_url, follow_redirects=False) as response:
                    if follow_redirects is True and response.next_request is not None:
                        next_url = response.next_request.url
                    else:
                        next_url = None
                    # nothing else to do here, but using the context manager ensures that the
                    # response is always properly closed

        # FIXME: workaround for https://github.com/encode/httpx/discussions/2682#discussioncomment-5746317
        except ssl.SSLError as e:
            # do not domain.ssl_error if there was a redirect to a different domain
            last_domain = self.get_domain(history[-1])
            if domain.name != last_domain:
                logger.warning(f"URL {url} redirects to a different domain: {last_domain}")
                link.result = "needs user check"
                return
            elif "unable to get local issuer certificate" in str(e):
                # FIXME: this is a problem of the SSL library used by Python
                logger.warning(f"possible SSL error (unable to get local issuer certificate) for URL {url}")
                domain.ssl_error = str(e)
                link.result = "needs user check"
                return
            else:
                logger.error(f"SSL error ({e}) for URL {url}")
                domain.ssl_error = str(e)
                link.result = "bad"
                return
        except httpx.ConnectError as e:
            last_domain = self.get_domain(history[-1])
            if str(e).startswith("[SSL:"):
                # do not record an error if there was a redirect to a different domain
                if domain.name != last_domain:
                    logger.warning(f"URL {url} redirects to a different domain: {last_domain}")
                    link.result = "needs user check"
                    return
                elif "unable to get local issuer certificate" in str(e):
                    # FIXME: this is a problem of the SSL library used by Python
                    logger.warning(f"possible SSL error (unable to get local issuer certificate) for URL {url}")
                    domain.ssl_error = str(e)
                    link.result = "needs user check"
                    return
                else:
                    logger.error(f"SSL error ({e}) for URL {url}")
                    domain.ssl_error = str(e)
                    link.result = "bad"
                    return
            if "no address associated with hostname" in str(e).lower() \
                    or "name or service not known" in str(e).lower():
                # do not record an error if there was a redirect to a different domain
                if domain.name == last_domain:
                    logger.error(f"domain name could not be resolved for URL {url}")
                    domain.resolved = False
                    link.result = "bad"
                else:
                    logger.error(f"URL {url} redirects to a domain that could not be resolved: {last_domain}")
                    link.result = "needs user check"
                return
            # other connection error - indeterminate
            logger.warning(f"connection error for URL {url}")
            link.text_status = "connection error"
            link.result = "needs user check"
            return
        except httpx.TooManyRedirects as e:
            logger.error(f"TooManyRedirects error ({e}) for URL {url}")
            link.text_status = "too many redirects"
            link.result = "bad"
            return
        # it seems that httpx does not capture all exceptions, e.g. anyio.EndOfStream
        #except httpx.RequestError as e:
        except Exception as e:
            # e.g. ReadTimeout has no message in the async version,
            # see https://github.com/encode/httpx/discussions/2681
            msg = str(e)
            if not msg:
                msg = type(e)
            # base class exception - indeterminate
            logger.error(f"URL {url} could not be checked due to {msg}")
            link.text_status = f"could not be checked due to {msg}"
            link.result = "needs user check"
            return

        # set common attributes from the response
        link.http_status = response.status_code
        link.check_duration = response.elapsed
        if "Server" in response.headers:
            link.domain.server = response.headers["Server"]

        # check special domains
        if link.http_status in domains_with_ignored_status.get(url.host, []):
            logger.warning(f"status code {response.status_code} for URL {url}")
            link.result = "needs user check"
            return

        # set the result
        if response.status_code >= 200 and response.status_code < 300:
            logger.debug(f"status code {response.status_code} for URL {url}")
            link.result = "OK"
        elif response.status_code >= 400 and response.status_code < 500:
            # detect cloudflare captcha https://github.com/pielco11/fav-up/issues/13
            if "CF-Chl-Bypass" in response.headers:
                logger.warning(f"CloudFlare CAPTCHA detected for URL {url}")
                link.text_status = "CloudFlare CAPTCHA"
                link.result = "needs user check"
            # CloudFlare sites may have custom firewall rules that block non-browser requests
            # with error 1020 https://github.com/codemanki/cloudscraper/issues/222
            elif response.status_code == 403 and response.headers.get("Server", "").lower() == "cloudflare":
                logger.warning(f"status code 403 for URL {url} backed up by CloudFlare does not mean anything")
                link.text_status = "CloudFlare shit"
                link.result = "needs user check"
            elif response.status_code == 429:
                # HTTP 429 (Too Many Requests) is not "bad"
                logger.warning(f"status code {response.status_code} for URL {url}")
                link.result = "needs user check"
            else:
                logger.error(f"status code {response.status_code} for URL {url}")
                link.result = "bad"
        else:
            logger.warning(f"status code {response.status_code} for URL {url}")
            link.result = "needs user check"

    async def check_link(self, link: LinkCheck):
        # preprocessing - check if the URL is valid
        url = link.url
        if not self.is_checkable_url(url):
            return
        url = self.normalize_url(url)

        # reset attributes
        link.last_check = datetime.datetime.utcnow()
        link.check_duration = None
        link.http_status = None
        link.server = None
        link.text_status = None
        link.result = None

        # skip the check if the domain is known to be invalid
        domain = link.domain
        if domain.last_check is not None and domain.last_check > link.last_check - datetime.timedelta(hours=1):
            # NOTE: ssl_error is not checked here because it is not always bad (there is a false positive)
            if domain.resolved is False:  # or domain.ssl_error is not None:
                link.result = "bad"
                return

        # proceed with the actual check
        await self.check_url(domain, link, url)

    async def lock_domain_and_check_link(self, semaphore, domain_locks, link: LinkCheck):
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
    def _get_domain_locks(domains):
        locks = {}
        # create separate lock for each domain
        for domain in domains:
            locks[domain.name] = asyncio.Lock()

        # merge locks for all *.sourceforge.net subdomains
        # (otherwise we often get HTTP status 429 Too Many Requests)
        common_lock = locks.setdefault("sourceforge.net", asyncio.Lock())
        for domain in locks.keys():
            if domain.endswith(".sourceforge.net"):
                locks[domain] = common_lock

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
        for domain in locks.keys():
            for se_domain in se_domains:
                if domain == se_domain or domain.endswith("." + se_domain):
                    locks[domain] = common_lock

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

        logger.info(f"Checking the status of {len(links)} URLs (success is logged with DEBUG level)...")

        # use a semaphore to limit the number of "active workers" in the task group
        semaphore = asyncio.Semaphore(100)

        async def async_exec():
            async with asyncio.TaskGroup() as tg:
                for link in links:
                    tg.create_task(self.lock_domain_and_check_link(semaphore, locks, link))

        if tqdm is not None:
            # initialize tqdm progressbar
            self.progress = tqdm.tqdm(total=len(links))
            with tqdm.contrib.logging.logging_redirect_tqdm():
                asyncio.run(async_exec())
            self.progress.close()
        else:
            asyncio.run(async_exec())
