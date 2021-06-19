#! /usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database
from ws.utils import range_by_days

def plot_setup(title="", ylabel="edits"):
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111)
    plt.title(title)
    plt.xlabel("date")
    plt.ylabel(ylabel)

    # x-ticks formatting
    plt.gca().xaxis.set_major_formatter(mpl.dates.DateFormatter('%Y-%m-%d'))
    plt.gca().xaxis.set_major_locator(mpl.dates.MonthLocator(interval=3))
    plt.tick_params(axis="x", which="both", direction="out")

    # y-ticks
    plt.gca().yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=10))

    # show grid
    plt.grid(True, which="both")

    return ax

def plot_revisions(ax, revisions, label):
    timestamps = sorted(revision["timestamp"] for revision in revisions)

    # construct an array of bin edges, one bin per day
    bin_edges = range_by_days(timestamps[0], timestamps[-1])

    # "bin" the timestamps (this will implicitly bin also the revisions)
    # NOTE: np.digitize returns a list of bin indexes for each revision
    bin_indexes = np.digitize(mpl.dates.date2num(timestamps), mpl.dates.date2num(bin_edges))

    # the returned indexes are 1-based indices!!! so let's turn them into 0-based
    bin_indexes = np.subtract(bin_indexes, 1)

    # since it is calculated by counting revisions in each bin, it is enough to count the indexes
    bin_data, _ = np.histogram(bin_indexes, bins=range(len(bin_edges)))

    # create cummulative sum
    bin_data = np.cumsum(bin_data)

    # xticks have to be rotated right before the plt.plot() call (wtf..)
    plt.xticks(rotation="vertical")
    line, = ax.plot(mpl.dates.date2num(bin_edges[:-1]), bin_data, label=label, linewidth=1.5)
    return line

def plot_logs(ax, line, logs):
    color = line.get_color()
    for log in logs:
        x = mpl.dates.date2num(log["timestamp"])
        y = np.interp(x, line._x, line._y)
        ax.plot(x, y, "o", color=color)
        labels = []
        for group in log["params"]["newgroups"]:
            labels.append("+{}".format(group))
        for group in log["params"]["oldgroups"]:
            labels.append("-{}".format(group))
        ax.annotate("\n".join(labels), xy=(x, y), xytext=(5, 0), textcoords="offset points", ha="left", va="top")

def plot_save(fname):
    plt.savefig(fname, dpi=192)

if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser()
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = ws.config.parse_args()

    api = API.from_argparser(args)
    require_login(api)
    db = Database.from_argparser(args)

    users = ["Alad", "Fengchao", "Indigo", "Kynikos", "Lahwaacz", "Lonaowna", "Nl6720"]

    all_logs = list(db.query(list="logevents", letype="rights", ledir="newer"))

    ax = plot_setup()
    lines = []
    for user in users:
        revs = list(db.query(list="allrevisions", arvlimit="max", arvprop={"timestamp"}, arvuser=user))
        revs += list(db.query(list="alldeletedrevisions", adrlimit="max", adrprop={"timestamp"}, adruser=user))
        line = plot_revisions(ax, revs, user)
        lines.append(line)
        logs = [log for log in all_logs if log["title"] == "User:{}".format(user)]
        plot_logs(ax, line, logs)
    plt.legend(handles=lines, loc="upper left")
#    plot_save("admins.png")
    plt.show()
