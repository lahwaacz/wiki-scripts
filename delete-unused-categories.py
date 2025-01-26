#! /usr/bin/env python3

from ws.client import API
from ws.interactive import ask_yesno, require_login
from ws.utils import RateLimited, dmerge


@RateLimited(1, 1)
def delete_page(api, title, pageid):
    print("Deleting page '{}' (pageid={})".format(title, pageid))
    api.call_with_csrftoken(action="delete", pageid=pageid, reason="Unused category", tags="wiki-scripts")

def main(args, api):
    unused_categories = [p["title"] for p in api.list(list="querypage", qppage="Unusedcategories", qplimit="max")]

    result = {}
    query = api.call_api_autoiter_ids(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", titles=unused_categories)

    for chunk in query:
        dmerge(chunk, result)

    pages = result["pages"]
    for page in sorted(pages.values(), key=lambda p: p["title"]):
        title = page["title"]
        pageid = page["pageid"]
        content = page["revisions"][0]["slots"]["main"]["*"]

        print()
        print(f"Unused category title: {title}")
        print(f"Content:\n{content}\n")
        delete = ask_yesno("Delete the page?")
        if delete is True:
            delete_page(api, title, pageid)

if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser(description="Delete unused categories (interactive)")
    API.set_argparser(argparser)

    args = ws.config.parse_args(argparser)

    api = API.from_argparser(args)
    require_login(api)

    main(args, api)
