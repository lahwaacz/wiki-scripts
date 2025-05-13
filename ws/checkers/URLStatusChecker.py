# TODO:
# - intel.com and its subdomains are returning false 404

import asyncio
import datetime
import ipaddress
import logging
import ssl
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from ws.utils import HTTPXAsyncClient

__all__ = ["URLStatusChecker", "Domain", "LinkCheck"]

logger = logging.getLogger(__name__)


# dataclass that *may* be mapped imperatively with SQLAlchemy ORM
# https://docs.sqlalchemy.org/en/20/orm/dataclasses.html#mapping-pre-existing-dataclasses-using-imperative-mapping
# NOTE: must be kept in sync with the imperative table defined in ws.db.schema
@dataclass
class Domain:
    # domain name
    name: str
    # timestamp of the last check
    last_check: datetime.datetime | None = None
    # flag indicating if the domain has been resolved at the time of the check
    resolved: bool | None = None
    # value of the "Server" response header
    server: str | None = None
    # record of the SSLError exception if it occurred during the check
    ssl_error: str | None = None

    # for backref relationship mapping
    url_checks: list["LinkCheck"] = field(default_factory=list)

    def __repr__(self):
        return f'Domain("{self.name},{self.last_check},{self.resolved},{self.server},{self.ssl_error}")'


# dataclass that *may* be mapped imperatively with SQLAlchemy ORM
# https://docs.sqlalchemy.org/en/20/orm/dataclasses.html#mapping-pre-existing-dataclasses-using-imperative-mapping
# NOTE: must be kept in sync with the imperative table defined in ws.db.schema
@dataclass
class LinkCheck:
    domain_name: str
    # for relationship mapping
    domain: Domain
    url: str

    last_check: datetime.datetime | None = None
    check_duration: datetime.timedelta | None = None
    # can be null if text_status is not null
    http_status: int | None = None
    # for "connection error", "too many redirects", "CloudFlare CAPTCHA", etc.
    text_status: str | None = None
    # result of the check: "ok", "bad", or "needs user check"
    result: str | None = None

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
    "bbs.archlinux.org": {
        403,
        404,
    },  # 403 for user profiles and 404 for pages that require login
    "crates.io": {404},  # returns 404 to the script but 200 in web browser
}


class URLStatusChecker:
    def __init__(
        self,
        *,
        timeout: int = 60,
        max_retries: int = 3,
        max_connections: int = 100,
        keepalive_expiry: int = 60,
    ):
        headers = {
            # fake user agent to bypass servers responding differently or not at all to non-browser user agents
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
            # github.com always returns 404 without the Accept header
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
        }

        # initialize the HTTPX clients
        # TODO: rename to async_client and add normal client
        self.client = HTTPXAsyncClient(
            headers=headers,
            timeout=timeout,
            retries=max_retries,
            max_connections=max_connections,
            keepalive_expiry=keepalive_expiry,
        )

    @staticmethod
    def is_checkable_url(url: str, *, allow_schemes: list[str] | None = None) -> bool:
        """Returns ``True`` if the URL can be checked or ``False``."""
        if allow_schemes is None:
            allow_schemes = ["http", "https"]

        try:
            # try to parse the URL - fails e.g. if port is not a number
            # reference: https://www.python-httpx.org/api/#url
            parsed_url = httpx.URL(url)
        except httpx.InvalidURL:
            logger.debug(f"skipped invalid URL: {url}")
            return False

        # skip unsupported schemes
        if parsed_url.scheme not in allow_schemes:
            logger.debug(f"skipped URL with unsupported scheme: {parsed_url}")
            return False
        # skip URLs with empty host, e.g. "http://" or "http://git@" or "http:///var/run"
        # (partial workaround for https://github.com/earwig/mwparserfromhell/issues/196 )
        if not parsed_url.host:
            logger.debug(f"skipped URL with empty host: {parsed_url}")
            return False
        # skip URLs with auth info (e.g. http://login.worker:PWD@api.bitcoin.cz:8332)
        if parsed_url.userinfo:
            logger.debug(f"skipped URL with authentication credentials: {parsed_url}")
            return False
        # skip links with top-level domains only
        # (in practice they would be resolved relative to the local domain, on the wiki they are used
        # mostly as a pseudo-variable like http://server/path or http://mydomain/path)
        if "." not in parsed_url.host:
            logger.debug(f"skipped URL with only top-level domain host: {parsed_url}")
            return False
        # skip links to invalid/blacklisted domains
        if (
            parsed_url.host
            == "pi.hole"  # pi-hole configuration involves setting pi.hole in /etc/hosts
            or parsed_url.host
            == "ui.reclaim"  # GNUnet - the domains works only with a browser extension
            or parsed_url.host.endswith(".onion")  # Tor
        ):
            logger.debug(
                f"skipped URL with invalid/blacklisted domain host: {parsed_url}"
            )
            return False
        # skip links to localhost
        if parsed_url.host == "localhost" or parsed_url.host.endswith(".localhost"):
            logger.debug(f"skipped URL to localhost: {parsed_url}")
            return False
        # skip links to reserved IP addresses
        try:
            addr = ipaddress.ip_address(parsed_url.host)
            for network in ipv4_reserved_networks:
                if addr in network:
                    logger.debug(
                        f"skipped URL to IP address from reserved network: {parsed_url}"
                    )
                    return False
        except ValueError:
            pass

        return True

    @staticmethod
    def normalize_url(url: httpx.URL | str) -> httpx.URL:
        url = httpx.URL(url)

        # drop the fragment from the URL (to optimize caching)
        url = url.copy_with(fragment=None)

        return url

    @staticmethod
    def get_domain(url: httpx.URL | str) -> str:
        url = httpx.URL(url)

        # httpx decodes punycodes for IDNs in .host, .raw_host is the original as bytes
        return url.raw_host.decode("utf-8")

    async def check_url(
        self,
        domain: Domain,
        link: LinkCheck,
        url: httpx.URL,
        *,
        follow_redirects: bool = True,
    ) -> None:
        history: list[httpx.URL] = []

        try:
            # We need to follow redirects with a manual loop, because they may lead to other
            # domains and we need to handle their status separately. httpx does not allow to
            # get response.history after an exception.
            next_url: httpx.URL | None = url
            while next_url is not None and len(history) <= self.client.max_redirects:
                history.append(next_url)
                # We need to use GET requests instead of HEAD, because many servers just return 404
                # (or do not reply at all) to HEAD requests. Instead, we skip the downloading of the
                # response body content by using ``stream`` interface.
                async with self.client.stream(
                    "GET", next_url, follow_redirects=False
                ) as response:
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
                logger.warning(
                    f"URL {url} redirects to a different domain: {last_domain}"
                )
                link.result = "needs user check"
                return
            elif "unable to get local issuer certificate" in str(e):
                # FIXME: this is a problem of the SSL library used by Python
                logger.warning(
                    f"possible SSL error (unable to get local issuer certificate) for URL {url}"
                )
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
                    logger.warning(
                        f"URL {url} redirects to a different domain: {last_domain}"
                    )
                    link.result = "needs user check"
                    return
                elif "unable to get local issuer certificate" in str(e):
                    # FIXME: this is a problem of the SSL library used by Python
                    logger.warning(
                        f"possible SSL error (unable to get local issuer certificate) for URL {url}"
                    )
                    domain.ssl_error = str(e)
                    link.result = "needs user check"
                    return
                else:
                    logger.error(f"SSL error ({e}) for URL {url}")
                    domain.ssl_error = str(e)
                    link.result = "bad"
                    return
            if (
                "no address associated with hostname" in str(e).lower()
                or "name or service not known" in str(e).lower()
            ):
                # do not record an error if there was a redirect to a different domain
                if domain.name == last_domain:
                    logger.error(f"domain name could not be resolved for URL {url}")
                    domain.resolved = False
                    link.result = "bad"
                else:
                    logger.error(
                        f"URL {url} redirects to a domain that could not be resolved: {last_domain}"
                    )
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
        # except httpx.RequestError as e:
        except Exception as e:
            # e.g. ReadTimeout has no message in the async version,
            # see https://github.com/encode/httpx/discussions/2681
            msg = str(e)
            if not msg:
                msg = str(type(e))
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
            elif (
                response.status_code == 403
                and response.headers.get("Server", "").lower() == "cloudflare"
            ):
                logger.warning(
                    f"status code 403 for URL {url} backed up by CloudFlare does not mean anything"
                )
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

    async def check_link(self, link: LinkCheck) -> None:
        # preprocessing - check if the URL is valid
        if not self.is_checkable_url(link.url):
            return
        url = self.normalize_url(link.url)

        # reset attributes
        link.last_check = datetime.datetime.now(datetime.UTC)
        link.check_duration = None
        link.http_status = None
        link.text_status = None
        link.result = None

        # skip the check if the domain is known to be invalid
        domain = link.domain
        if (
            domain.last_check is not None
            and domain.last_check > link.last_check - datetime.timedelta(hours=1)
        ):
            # NOTE: ssl_error is not checked here because it is not always bad (there is a false positive)
            if domain.resolved is False:  # or domain.ssl_error is not None:
                link.result = "bad"
                return

        # reset domain attributes
        domain.last_check = link.last_check
        domain.resolved = None
        domain.server = None
        domain.ssl_error = None

        # proceed with the actual check
        await self.check_url(domain, link, url)

    def check_link_sync(self, link: LinkCheck) -> None:
        """Synchronous variant of ``check_link``"""
        return asyncio.run(self.check_link(link))

    @lru_cache(maxsize=1024)
    def get_url_check(self, url: str) -> LinkCheck:
        """
        Get the status of given URL as a ``LinkCheck`` object.

        Note that this function is synchronous and cached only in memory (i.e.
        not in the SQL database). There is also no domain locking to avoid
        concurrent connections to the same domain.
        """
        domain_name = self.get_domain(url)
        domain = Domain(name=domain_name)  # TODO: cache this separately?
        link = LinkCheck(domain_name=domain_name, url=url, domain=domain)
        self.check_link_sync(link)
        return link
