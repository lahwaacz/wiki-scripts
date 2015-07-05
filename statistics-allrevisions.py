#! /usr/bin/env python3

# NOTE:
# * deleted revisions are not included
# * only diffable changes are recorded (edits and moves, not deletions)
# * bots vs nobots
# * different notion of active user ("calendar month" vs "30 days")
#
# TODO:
# * refactoring

import os.path
import json

from MediaWiki import API
import cache
from utils import parse_date
from MediaWiki.wikitable import *


# return list of datetime.date objects with items jumped by 1 month
def datetime_month_range(first, last):
    import datetime
    range_ = []
    first = datetime.date(first.year, first.month, 1)
    last = datetime.date(last.year, last.month, last.day)
    while first < last:
        range_.append(first)
        try:
            first = datetime.date(first.year, first.month + 1, 1)
        except ValueError:
            first = datetime.date(first.year + 1, 1, 1)
    range_.append(first)    # rightmost
    return range_

def plot_date_bars(bin_data, bin_edges, title, ylabel, fname):
    """
    Semi-generic function to plot a bar graph, x-label is fixed to "date" and the
    x-ticks are formatted accordingly.

    To plot a histogram, the histogram data must be calculated manually outside
    this function, either manually or using :py:func`numpy.histogram`.

    :param bin_data: list of data for each bin
    :param bin_edges: list of bin edges (:py:class:`datetime.date` objects), its
                      length must be ``len(data)+1``
    :param title: title of the plot
    :param ylabel: label of y-axis
    :param fname: output file name
    """
    import matplotlib.pyplot as plt
    from matplotlib.dates import date2num, num2date
    from matplotlib import ticker

    fig = plt.figure()
    plt.title(title)
    plt.xlabel("date")
    plt.ylabel(ylabel)

    # plot the bars, width of the bins is assumed to be fixed
    plt.bar(date2num(bin_edges[:-1]), bin_data, width=date2num(bin_edges[1])-date2num(bin_edges[0]))

    # x-ticks formatting
    plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(lambda numdate, _: num2date(numdate).strftime('%Y-%m-%d')))
    plt.gcf().autofmt_xdate()
    plt.tick_params(axis="x", which="both", direction="out")
    plt.xticks([date2num(ts) for ts in bin_edges if ts.month % 6 == 1])

    plt.savefig(fname, papertype="a4")

def create_histograms(revisions):
    """
    Build some histograms from the revisions data:
      - count of total edits per month since the wiki has been created
      - count of active users in each month

    Reference: http://stackoverflow.com/a/3035824 (highly adjusted)
    """
    import numpy as np
    from matplotlib.dates import date2num, num2date

    # list of timestamps for each revision
    timestamps = [parse_date(revision["timestamp"]) for revision in revisions]
    # alternatively exclude bots
#    timestamps = [parse_date(revision["timestamp"]) for revision in revisions if revision["user"] not in ["Kynikos.bot", "Lahwaacz.bot", "Strcat"]]

    # construct an array of bin edges, one bin per calendar month
    bin_edges = datetime_month_range(timestamps[0], timestamps[-1])

    # "bin" the timestamps (this will implicitly bin also the revisions)
    # NOTE: np.digitize returns a list of bin indexes for each revision
    bin_indexes = np.digitize(date2num(timestamps), date2num(bin_edges))

    # the returned indexes are 1-based indices!!! so let's turn them into 0-based
    bin_indexes = np.subtract(bin_indexes, 1)


    # histogram for all edits
    print("Plotting hist_alledits.png")
    # since it is calculated by counting revisions in each bin, it is enough to count
    # the indexes
    hist_alledits, _ = np.histogram(bin_indexes, bins=range(len(bin_edges)))

    plot_date_bars(hist_alledits, bin_edges, title="ArchWiki edits per month",
            ylabel="edit count", fname="stub/hist_alledits.png")
#    plot_date_bars(hist_alledits, bin_edges,
#            title="ArchWiki edits per month (without bots)", ylabel="edit count",
#            fname="stub/hist_alledits_nobots.png")


    # histogram for active users
    print("Plotting hist_active_users.png")
    hist_active_users = []
    num_bins = len(bin_edges) - 1
    for i in range(num_bins):
        # array of indexes for revisions in current bin
        current_bin, = np.where(bin_indexes == i)
        active_users = list(set([revisions[ii]["user"] for ii in current_bin]))
        hist_active_users.append(len(active_users))

    plot_date_bars(hist_active_users, bin_edges,
            title="ArchWiki active users per month", ylabel="active users",
            fname="stub/hist_active_users.png")


# TODO:
#   record date of longest streak
def get_streaks(revisions_iterator, today):
    """
    Calculate the longest and current streak based on given user's revisions. Streaks are
    recognized based on UTC day, but edits made UTC-yesterday are counted into the current
    streak. This way running the script just after UTC midnight will not reset current
    streaks to 0.

    :param revisions_iterator: an iterator object yielding revision dictionaries for given user
    :returns: (longest, current) tuple of streak values (in days)
    """
    longest_streak = 0
    current_streak = 0

    def _streak(revision):
        """ Return streak ID number for given revision.
            Side effect: revision["timestamp"] is parsed and replaced with `datetime.date` object
        """
        ts = parse_date(revision["timestamp"])
        date = datetime.date(ts.year, ts.month, ts.day)
        revision["timestamp"] = date

        # check if new streak starts
        if _streak.prev_date is None or date - _streak.prev_date > datetime.timedelta(days=1):
            _streak.id += 1

        _streak.prev_date = date
        return _streak.id

    _streak.prev_date = None
    _streak.id = 0

    # group revisions by streaks
    streak_groups = itertools.groupby(revisions_iterator, key=_streak)

    for _, streak in streak_groups:
        streak = list(streak)
        current_streak = (streak[-1]["timestamp"] - streak[0]["timestamp"]).days + 1

        # continuously update longest streak
        if current_streak > longest_streak:
            longest_streak = current_streak

        # check if the last edit has been made on this UTC day
        if today - streak[-1]["timestamp"] > datetime.timedelta(days=1):
            current_streak = 0

    return longest_streak, current_streak


if __name__ == "__main__":
    # TODO: take command line arguments
    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

    db = cache.AllRevisionsProps(api)
#    create_histograms(db["revisions"])


    import itertools
    import operator
    import datetime

    # current UTC date
    utcnow = datetime.datetime.utcnow()
    today = datetime.date(utcnow.year, utcnow.month, utcnow.day)

    # sort revisions by multiple keys: 1. user, 2. timestamp
    # this way we can group the list by users and iterate through user_revisions to
    # calculate all streaks, record the longest streak and determine the current streak
    # at the end (the last calculated streak or 0)
    revisions = sorted(db["revisions"], key=lambda r: (r["user"], r["timestamp"]))
    revisions_groups = itertools.groupby(revisions, key=lambda r: r["user"])
    streaks = []
    for user, user_revisions in revisions_groups:
        longest, current = get_streaks(user_revisions, today)
        # limit the results
        if longest > 1 or current > 1:
            streaks.append({"user": user, "longest": longest, "current": current})

    streaks.sort(key=lambda streak: streak["longest"])

    igetter = operator.itemgetter("user", "current", "longest")
    fields = ["User", "Current streak", "Longest streak"]
    rows = [igetter(r) for r in streaks]

    print(Wikitable.assemble(fields, rows))
