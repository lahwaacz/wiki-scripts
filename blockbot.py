#! /usr/bin/env python3

from pprint import pprint
import datetime
import time
import random
import string
import re

from ws.core import API, APIError
from ws.core.rate import RateLimited
from ws.interactive import require_login, ask_yesno
from ws.utils import parse_date, list_chunks


def is_blocked(api, user):
    response = api.call_api(action="query", list="allusers", aufrom=user, auto=user, auprop="blockinfo")
    return "blockid" in response["allusers"][0]

def block_user(api, user):
    @RateLimited(1, 3)
    def block():
        print("Blocking user '{}' ...".format(user))
        api.call_api(action="block", user=user, reason="spamming", nocreate="1", autoblock="1", noemail="1", token=api._csrftoken)
    if is_blocked(api, user):
        print("User '{}' is already blocked.".format(user))
        return
    block()

@RateLimited(1, 1)
def delete_page(api, title, pageid):
    print("Deleting page '{}' (pageid={})".format(title, pageid))
    api.call_api(action="delete", pageid=pageid, reason="spam", token=api._csrftoken)

class Blockbot:
    def __init__(self, api, spam_phrases, interactive=True):
        self.api = api
        self.interactive = interactive

        # TODO: assert len(spam_phrases) > 0
        self.spam_phrases = spam_phrases
        for phrase in spam_phrases[:]:
            self.spam_phrases.append(phrase.replace(" ", ""))

        # TODO: make configurable
        self.spam_occurrences_threshold = 5
        self.timeout_func = lambda: random.uniform(180, 360)
        self.punctuation_regex = re.compile('[%s]' % re.escape(string.punctuation))

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        group = argparser.add_argument_group(title="script parameters")
        group.add_argument("--interactive", default=True, metavar="BOOL", type=ws.config.argtype_bool, help="Enables interactive mode (default: %(default)s)")
        group.add_argument("--spam-phrases", action="append", required=True, metavar="STR", help="A phrase considered as spam (this option can be specified multiple times).")

    @classmethod
    def from_argparser(klass, args, api=None):
        if api is None:
            api = API.from_argparser(args)
        return klass(api, args.spam_phrases, args.interactive)

    def is_spam(self, title, text):
        title = self.punctuation_regex.sub("", title)
        text = self.punctuation_regex.sub("", text)
        for phrase in self.spam_phrases:
            if phrase in title.lower():
                return True
            if text.lower().count(phrase) > self.spam_occurrences_threshold:
                return True
        return False

    def filter_pages(self, pages):
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
                pprint({"title": page["title"], "content": content, "timestamp": rev["timestamp"]})
                if self.interactive and ask_yesno("Proceed with user account blocking and deletion?") is False:
                    continue

                # block the account
                block_user(self.api, rev["user"])
                if rev["parentid"] == 0:
                    # first revision, delete whole page
                    delete_page(self.api, page["title"], page["pageid"])
                else:
                    # TODO: if all revisions of the page are spam, delete the whole page
                    print("Warning: deletion of individual revisions is not implemented!")
            else:
                print("Page '{}' is not a spam.".format(page["title"]))

    def main_loop(self):
        require_login(self.api)
        if "block" not in self.api.user_rights:
            print("Your account does not have the 'block' right.")
            return False
        if "delete" not in self.api.user_rights:
            print("Your account does not have the 'delete' right.")
            return False

        start = datetime.datetime.utcnow() - datetime.timedelta(days=1)

        while True:
            # drop microseconds (included in the default format string, but MediaWiki does not like it)
            start -= datetime.timedelta(microseconds=start.microsecond)

            try:
                start2 = datetime.datetime.utcnow()
                pages = self.api.generator(generator="recentchanges", grcstart=start, grcdir="newer", grcshow="unpatrolled", grclimit="max", prop="revisions", rvprop="ids|timestamp|user|comment|content")
                self.filter_pages(pages)

            # TODO: generalize retry on "badtoken" error (the following branch is from API.edit)
            except APIError as e:
                # csrftoken can be used multiple times, but expires after some time,
                # so try to get a new one *once*
                if e.server_response["code"] == "badtoken":
                    # reset the cached csrftoken and try again
                    del self.api._csrftoken
                    # FIXME: does not count failures !!!
                    continue
                raise
            except (ConnectionError, TimeoutError) as e:
                # query failed, set short timeout and retry from the previous timestamp
                timeout = 30
                # FIXME: better representation of the exception as str()
                print("Catched {} exception, sleeping {} seconds before retrying...".format(repr(e), timeout))
            else:
                # query succeeded, shift start timestamp and set timeout
                start = start2
                timeout = self.timeout_func()
                print("{}  Sleeping for {:.3g} seconds...".format(start, timeout))

            try:
                time.sleep(timeout)
            except KeyboardInterrupt:
                try:
                    # short timeout to allow interruption of the main loop
                    time.sleep(0.5)
                except KeyboardInterrupt as e:
                    raise e from None

#        # go through recently deleted revisions, detect spam and block the remaining users
#        logs = api.list(list="logevents", letype="delete", lelimit="max", ledir="newer", lestart=start)
#        titles = [log["title"] for log in logs if log["comment"].lower().startswith("spam")]
#        for chunk in list_chunks(titles, 50):
#            result = api.call_api(action="query", titles="|".join(chunk), prop="deletedrevisions", drvprop="ids|timestamp|user|comment|content", rawcontinue="")
#            pages = result["pages"].values()
#            for page in pages:
#                if "deletedrevisions" not in page:
#                    # empty prop in generator due to continuation
#                    continue
#                rev = page["deletedrevisions"][0]
#                if not is_blocked(api, rev["user"]):
#                    ans = ask_yesno("Block user '{}' who created page '{}'?")
#                    if ans is True:
#                        block_user(api, rev["user"])

        return True

if __name__ == "__main__":
    import sys
    import ws.config

    blockbot = ws.config.object_from_argparser(Blockbot, description="blockbot")
    sys.exit(not blockbot.main_loop())
