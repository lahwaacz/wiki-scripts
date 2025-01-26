#! /usr/bin/env python3

from ws.client import API


def dump(api, outfile, timestamp_start):
    # check that the index.php URL is configured
    assert api.index_url is not None, "The index.php URL must be configured."

    print("Fetching list of all pages...")
    pages = []
    namespaces = [ns for ns in api.site.namespaces.keys() if ns >= 0]
    for ns in namespaces:
        pages += list([page["title"] for page in api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)])

    print("Calling Special:Export...")
    # ref: http://www.mediawiki.org/wiki/Manual:Parameters_to_Special:Export
    data = {
        "title": "Special:Export",
        "pages": "\n".join(pages),
        "offset": timestamp_start,
    }
    response = api.call_index(method="POST", data=data, stream=True)
    chunk_size = 1024 * 1024

    # handle download stream
    with open(outfile, 'wb') as fd:
        for chunk in response.iter_content(chunk_size):
            fd.write(chunk)


if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Check pages in the user namespace")

    # TODO: take parameters from command line and make sure that the timestamp is in the format '%Y-%m-%dT%H:%M:%SZ'
    dump(api, "dump-test.xml", "2014-07-01T00:00:00Z")
