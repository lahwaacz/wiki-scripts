#! /usr/bin/env python3

# NOTE:
# * only diffable changes are recorded (edits and moves, not deletions)
# * bots vs nobots
# * different notion of active user ("calendar month" vs "30 days")

import logging

from ws.client import API
import ws.cache
from ws.utils import range_by_months

logger = logging.getLogger(__name__)

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

    plt.figure()  # clear previous figure
    plt.title(title)
    plt.xlabel("date")
    plt.ylabel(ylabel)

    # plot the bars, width of the bins is assumed to be fixed
    plt.bar(date2num(bin_edges[:-1]), bin_data, width=date2num(bin_edges[1]) - date2num(bin_edges[0]))

    # x-ticks formatting
    plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(lambda numdate, _: num2date(numdate).strftime('%Y-%m-%d')))
    plt.gcf().autofmt_xdate()
    plt.tick_params(axis="x", which="both", direction="out")
    plt.xticks([date2num(ts) for ts in bin_edges if ts.month % 12 == 1])

    plt.savefig(fname, papertype="a4")

def create_histograms(revisions):
    """
    Build some histograms from the revisions data:
      - count of total edits per month since the wiki has been created
      - count of active users in each month

    Reference: http://stackoverflow.com/a/3035824 (highly adjusted)
    """
    import numpy as np
    from matplotlib.dates import date2num

    # list of timestamps for each revision
    timestamps = [revision["timestamp"] for revision in revisions]
    # alternatively exclude bots
#    timestamps = [revision["timestamp"] for revision in revisions if revision["user"] not in ["Kynikos.bot", "Lahwaacz.bot", "Strcat"]]

    # construct an array of bin edges, one bin per calendar month
    bin_edges = range_by_months(timestamps[0], timestamps[-1])

    # "bin" the timestamps (this will implicitly bin also the revisions)
    # NOTE: np.digitize returns a list of bin indexes for each revision
    bin_indexes = np.digitize(date2num(timestamps), date2num(bin_edges))

    # the returned indexes are 1-based indices!!! so let's turn them into 0-based
    bin_indexes = np.subtract(bin_indexes, 1)


    # histogram for all edits
    logger.info("Plotting hist_alledits.png")
    # since it is calculated by counting revisions in each bin, it is enough to count
    # the indexes
    hist_alledits, _ = np.histogram(bin_indexes, bins=range(len(bin_edges)))

    plot_date_bars(hist_alledits, bin_edges, title="ArchWiki edits per month",
            ylabel="edit count", fname="stub/hist_alledits.png")
#    plot_date_bars(hist_alledits, bin_edges,
#            title="ArchWiki edits per month (without bots)", ylabel="edit count",
#            fname="stub/hist_alledits_nobots.png")


    # histogram for active users
    logger.info("Plotting hist_active_users.png")
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


if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Create histogram charts for the statistics page")
    API.set_argparser(argparser)
    # TODO: script-specific arguments (e.g. output path)
    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = ws.cache.AllRevisionsProps(api, args.cache_dir)

    create_histograms(db["revisions"])
