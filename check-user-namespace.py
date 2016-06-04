#! /usr/bin/env python3

import itertools

from ws.core import API

def pages_in_namespace(api, ns):
    return api.generator(generator="allpages", gapnamespace=ns, gaplimit="max", prop="categories", clshow="!hidden")

def get_user_names(api):
    return [user["name"] for user in api.list(list="allusers", aulimit="max")]

def main(api):
    user_pages = itertools.chain(pages_in_namespace(api, 2), pages_in_namespace(api, 3))
    users = get_user_names(api)

    for page in user_pages:
        # check if corresponding user exists
        basepage = page["title"].split("/", 1)[0]
        user = basepage.split(":", 1)[1]
        if user not in users:
            print("* Page [[{}]] exists but username '{}' does not".format(page["title"], user))

        # user pages shall not be categorized
        if "categories" in page:
            if len(page["categories"]) > 0:
                print("* Page [[{}]] is categorized: {}".format(page["title"], list(cat["title"] for cat in page["categories"])))

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Check pages in the user namespace")
    main(api)
