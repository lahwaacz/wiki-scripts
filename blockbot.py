#! /usr/bin/env python3

import argparse
import datetime
import random
import re
import string
import time
from pprint import pprint
from typing import Any, Iterable, Self

import httpx

from ws.client import API
from ws.config import ConfigurableObject
from ws.interactive import ask_yesno, require_login
from ws.utils import RateLimited


def is_blocked(api: API, user: str) -> bool:
    response = api.call_api(
        action="query", list="allusers", aufrom=user, auto=user, auprop="blockinfo"
    )
    return "blockid" in response["allusers"][0]


def block_user(api: API, user: str) -> None:
    @RateLimited(1, 3)
    def block() -> None:
        print(f"Blocking user '{user}' ...")
        api.call_with_csrftoken(
            action="block",
            user=user,
            reason="spamming",
            nocreate="1",
            autoblock="1",
            noemail="1",
        )

    if is_blocked(api, user):
        print(f"User '{user}' is already blocked.")
        return
    block()


@RateLimited(1, 1)
def delete_page(api: API, title: str, pageid: int) -> None:
    print(f"Deleting page '{title}' (pageid={pageid})")
    api.call_with_csrftoken(action="delete", pageid=pageid, reason="spam")


class Blockbot(ConfigurableObject):
    def __init__(
        self,
        api: API,
        spam_phrases: list[str],
        spam_occurrences_threshold: int = 5,
        interactive: bool = True,
    ):
        self.api = api
        self.interactive = interactive
        self.spam_occurrences_threshold = spam_occurrences_threshold

        # TODO: assert len(spam_phrases) > 0
        self.spam_phrases = spam_phrases
        for phrase in spam_phrases[:]:
            self.spam_phrases.append(phrase.replace(" ", ""))

        # TODO: make configurable
        self.timeout_func = lambda: random.uniform(180, 360)
        self.punctuation_regex = re.compile("[%s]" % re.escape(string.punctuation))

    @staticmethod
    def set_argparser(argparser: argparse.ArgumentParser) -> None:
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        group = argparser.add_argument_group(title="script parameters")
        group.add_argument(
            "--interactive",
            default=True,
            metavar="BOOL",
            type=ws.config.argtype_bool,
            help="Enables interactive mode (default: %(default)s)",
        )
        group.add_argument(
            "--spam-phrases",
            action="append",
            required=True,
            metavar="STR",
            help="A phrase considered as spam (this option can be specified multiple times).",
        )
        group.add_argument(
            "--spam-occurrences-threshold",
            type=int,
            default=5,
            help="Minimal number of phrases occurring on a page that triggers the spam filter.",
        )

    @classmethod
    def from_argparser(
        cls: type[Self], args: argparse.Namespace, api: API | None = None
    ) -> Self:
        if api is None:
            api = API.from_argparser(args)
        return cls(
            api, args.spam_phrases, args.spam_occurrences_threshold, args.interactive
        )

    def is_spam(self, title: str, text: str) -> bool:
        title = self.punctuation_regex.sub("", title)
        text = self.punctuation_regex.sub("", text)
        for phrase in self.spam_phrases:
            if phrase in title.lower():
                return True
            if text.lower().count(phrase) > self.spam_occurrences_threshold:
                return True
        return False

    def filter_pages(self, pages: Iterable[dict[str, Any]]) -> None:
        for page in pages:
            if "revisions" in page:
                # skip truncated results (due to PHP's 8MiB limit)
                if len(page["revisions"]) == 0:
                    continue
                rev = page["revisions"][0]
            else:
                # empty prop in generator due to continuation
                continue

            content = rev["*"]
            if self.is_spam(page["title"], content):
                print("Detected spam:")
                pprint(
                    {
                        "title": page["title"],
                        "content": content,
                        "timestamp": rev["timestamp"],
                    }
                )
                if (
                    self.interactive
                    and ask_yesno("Proceed with user account blocking and deletion?")
                    is False
                ):
                    continue

                # block the account
                block_user(self.api, rev["user"])
                if rev["parentid"] == 0:
                    # first revision, delete whole page
                    delete_page(self.api, page["title"], page["pageid"])
                else:
                    # TODO: if all revisions of the page are spam, delete the whole page
                    print(
                        "Warning: deletion of individual revisions is not implemented!"
                    )
            else:
                print(f"Page '{page['title']}' is not a spam.")

    def main_loop(self) -> bool:
        require_login(self.api)
        if "block" not in self.api.user.rights:
            print("Your account does not have the 'block' right.")
            return False
        if "delete" not in self.api.user.rights:
            print("Your account does not have the 'delete' right.")
            return False

        start = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
        timeout: int | float

        while True:
            try:
                start2 = datetime.datetime.now(datetime.UTC)
                pages = self.api.generator(
                    generator="recentchanges",
                    grcstart=start,
                    grcdir="newer",
                    grcshow="unpatrolled",
                    grclimit="max",
                    prop="revisions",
                    rvprop="ids|timestamp|user|comment|content",
                )
                self.filter_pages(pages)
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                # query failed, set short timeout and retry from the previous timestamp
                timeout = 30
                # FIXME: better representation of the exception as str()
                print(
                    f"Caught {e!r} exception, sleeping {timeout} seconds before retrying..."
                )
            else:
                # query succeeded, shift start timestamp and set timeout
                start = start2
                timeout = self.timeout_func()
                print(f"{start}  Sleeping for {timeout:.3g} seconds...")

            try:
                time.sleep(timeout)
            except KeyboardInterrupt:
                try:
                    # short timeout to allow interruption of the main loop
                    time.sleep(0.5)
                except KeyboardInterrupt as e:
                    raise e from None

        # # go through recently deleted revisions, detect spam and block the remaining users
        # logs = api.list(list="logevents", letype="delete", lelimit="max", ledir="newer", lestart=start)
        # titles = [log["title"] for log in logs if log["comment"].lower().startswith("spam")]
        # for chunk in list_chunks(titles, 50):
        #    result = api.call_api(action="query", titles="|".join(chunk), prop="deletedrevisions", drvprop="ids|timestamp|user|comment|content", rawcontinue="")
        #    pages = result["pages"].values()
        #    for page in pages:
        #        if "deletedrevisions" not in page:
        #            # empty prop in generator due to continuation
        #            continue
        #        rev = page["deletedrevisions"][0]
        #        if not is_blocked(api, rev["user"]):
        #            ans = ask_yesno("Block user '{}' who created page '{}'?")
        #            if ans is True:
        #                block_user(api, rev["user"])

        return True


if __name__ == "__main__":
    import sys

    import ws.config

    blockbot = ws.config.object_from_argparser(Blockbot, description="blockbot")
    sys.exit(not blockbot.main_loop())
