import datetime
import json
from typing import Any


class DatetimeEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if (
            isinstance(o, datetime.datetime)
            or isinstance(o, datetime.date)
            or isinstance(o, datetime.timedelta)
        ):
            return repr(o)
        else:
            return super().default(o)


def datetime_parser(dct: dict) -> dict:
    for k, v in dct.items():
        if isinstance(v, str) and v.startswith("datetime.") and v.endswith(")"):
            v = v[:-1]
            items = v.split("(", maxsplit=1)[1]
            args: list[int] = []
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
