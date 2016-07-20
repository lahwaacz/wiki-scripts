#! /usr/bin/env python3

from pprint import pprint

from ws.client import API

def main(api):
    logs = api.list(list="logevents", letype="newusers", lelimit="max", ledir="newer")
    logs = list(logs)

    pprint(logs)

    # these should be interesting
    #pprint([i for i in logs if i["action"] != "create"])

    print(len(logs))

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Print wiki log entries")
    main(api)
