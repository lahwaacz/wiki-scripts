#! /usr/bin/env python3

import datetime
import logging

import mwparserfromhell

from ws.interactive import edit_interactive

logger = logging.getLogger(__name__)

__all__ = ["AutoPage"]


class AutoPage:

    """
    A quick interface for maintaining automatic content on wiki pages.

    :param api: an :py:class:`ws.client.api.API` instance
    :param str title: the title of the initial page to use
    :param set fetch_titles:
        A set of titles whose content should be fetched from the wiki. These are
        the pages that will be updated later on; the page title should be
        switched by the :py:meth:`set_title` method. If ``None`` is supplied,
        ``fetch_titles`` defaults to ``[title]``.
    """

    def __init__(self, api, title=None, fetch_titles=None):
        self.api = api
        self.title = None
        self.wikicode = ""

        if fetch_titles is not None:
            self.fetch_pages(fetch_titles)
        else:
            self.fetch_pages([title])

        if title is not None:
            self.set_title(title)

    def fetch_pages(self, titles):
        """
        Fetch content of given pages from the API. As an optimization, as many
        pages as possible should be fetched in a single query.

        :param set titles: set of page titles
        """
        self.contents = {}
        self.timestamps = {}
        self.pageids = {}

        # TODO: query-continuation (query might be split due to extra long pages hitting PHP limits)
        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", titles="|".join(titles))
        for page in result["pages"].values():
            if "revisions" in page:
                title = page["title"]
                revision = page["revisions"][0]
                text = revision["*"]
                self.contents[title] = text
                self.timestamps[title] = revision["timestamp"]
                self.pageids[title] = page["pageid"]

        titles = set(titles)
        retrieved = set(self.contents.keys())
        if retrieved != titles:
            logger.error("unable to retrieve content of all pages: pages {} are missing, retrieved {}".format(titles - retrieved, retrieved))

    def set_title(self, title):
        """
        Set current title to ``title`` and parse its content. Unsaved changes to
        previous page will be lost. The content of the page should have been
        fetched by :py:meth:`fetch_pages`, otherwise :py:exc:`ValueError` will
        be raised.

        :param str title: the page title
        """
        if title not in self.contents.keys():
            raise ValueError("Content of page [[{}]] is not fetched.".format(title))
        self.title = title
        self.wikicode = mwparserfromhell.parse(self.contents[self.title])

    def get_tag_by_id(self, tag, id):
        """
        Finds a tag in the wikicode of the current page with given ID.

        :param str tag:
            The type of the :py:class:`Tag <mwparserfromhell.nodes.tag.Tag`,
            e.g. ``"div"`` or ``"table"``.
        :param str id:
            The value of the ``id`` attribute of the tag to be matched.
        :returns:
            A :py:class:`mwparserfromhell.nodes.tag.Tag` instance if found,
            otherwise ``None``.
        """
        for tag in self.wikicode.ifilter_tags(matches=lambda node: node.tag == tag):
            if tag.has("id"):
                id_ = tag.get("id")
                if id_.value == id:
                    return tag
        return None

    def is_old_enough(self, min_interval=datetime.timedelta(0), strip_time=False):
        """
        Checks if the page on the wiki is old enough to be updated again.

        :param datetime.timedelta min_interval:
            Minimum desired interval between two consecutive updates.
        :param bool strip_time:
            If ``True``, time is stripped from the UTC timestamps and only the
            dates are compared.
        :returns: ``True`` if the wiki page is older than ``min_interval``.
        """
        utcnow = datetime.datetime.utcnow()
        if strip_time is False:
            delta = utcnow - self.timestamps[self.title]
        else:
            delta = utcnow.date() - self.timestamps[self.title].date()
        return delta >= min_interval

    def save(self, edit_summary, interactive=False, **kwargs):
        """
        Saves the updated wikicode of the page to the wiki.

        :param str edit_summary: Summary of the change.
        :param bool interactive:
            If ``True``, calls :py:func:`ws.interactive.edit_interactive` to ask
            the user before making the change; otherwise calls
            :py:meth:`API.edit <ws.client.api.API.edit>` directly.
        :param kwargs: Additional keyword arguments passed to the API query.
        """
        text_new = str(self.wikicode)
        if self.contents[self.title] != text_new:
            # use bot=1 iff it makes sense
            kwargs["bot"] = "1"
            if "bot" not in self.api.user.rights:
                del kwargs["bot"]

            if interactive is True:
                edit_interactive(self.api, self.title, self.pageids[self.title], self.contents[self.title], text_new, self.timestamps[self.title], edit_summary, **kwargs)
            else:
                self.api.edit(self.title, self.pageids[self.title], text_new, self.timestamps[self.title], edit_summary, **kwargs)
        else:
            logger.info("Page [[{}]] is already up to date.".format(self.title))
