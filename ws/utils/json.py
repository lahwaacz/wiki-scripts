#! /usr/bin/env python3

import json
import datetime

class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if (isinstance(obj, datetime.datetime) or
            isinstance(obj, datetime.date) or
            isinstance(obj, datetime.timedelta)):
            return repr(obj)
        else:
            return super(DateTimeEncoder, self).default(obj)

def datetime_parser(dct):
    for k, v in dct.items():
        if isinstance(v, str) and v.startswith("datetime.") and v.endswith(")"):
            v = v[:-1]
            items = v.split("(", maxsplit=1)[1]
            args = []
            for i in items.split(","):
                try:
                    args.append(int(i.strip()))
                except ValueError:
                    continue
            if not args:
                continue
            if v.startswith("datetime.datetime("):
                dct[k] = datetime.datetime(*args)
            elif v.startswith("datetime.date("):
                dct[k] = datetime.date(*args)
            elif v.startswith("datetime.timedelta("):
                dct[k] = datetime.timedelta(*args)
    return dct
