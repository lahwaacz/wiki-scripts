#! /usr/bin/env python3

import datetime
import logging
import numpy as np
import pandas as pd

import bar_chart_race as bcr

from ws.db.database import Database

logger = logging.getLogger(__name__)


def fetch_revisions(db):
    revs = list(db.query(list="allrevisions", arvlimit="max", arvprop={"ids", "timestamp", "user"}))
    # TODO: this should be reconsidered, the "MediaWiki default" user is included here and some deleted revisions were pruned from the server...
    #revs += list(db.query(list="alldeletedrevisions", adrlimit="max", adrprop={"ids", "timestamp", "user"}))

    revs = pd.DataFrame(revs)
    # select only relevant columns (timestamp for rolling, user for grouping, revid for counting)
    revs = revs[["timestamp", "user", "revid"]]
    # sort by timestamp
    revs = revs.sort_values("timestamp")
    # rename "revid" to "revisions" as counting discards the "id" semantics
    revs = revs.rename(columns={"revid": "revisions"})
    return revs


def get_rolling_revisions(revs, *, period_days=30):
    # group by user and resaple to daily periods (used later for rolling counts and visualization)
    daily_revs = revs.groupby("user").resample("1d", on="timestamp", include_groups=False).count()
    # change back to previous format
    daily_revs = daily_revs.reset_index()

    # group by user and compute a rolling sum on the daily revision counts
    rolling_revs = daily_revs.groupby("user").rolling(f"{period_days}d", on="timestamp").sum()
    # change back to previous format
    rolling_revs = rolling_revs.reset_index().drop("level_1", axis="columns")

    return rolling_revs


def prune_rolling_data(df, *, nlargest, start_date=None):
    # select only n largest entries per timestamp
    pruned = df.sort_values("timestamp").groupby("timestamp").revisions.nlargest(nlargest)
    # get the original index values
    pruned_idx = pruned.reset_index()["level_1"]
    # filter the input dataframe
    df = df.iloc[pruned_idx]
    if start_date is None:
        return df
    return df[df["timestamp"] >= start_date]


def fill_timestamps(df, *, period_days=30):
    # fill all missing timestamps for all users
    # https://stackoverflow.com/a/44979696/4180822
    # NOTE: it is important to do this only after pruning the dataframe,
    #       otherwise this takes too much memory with ArchWiki data
    df = df.set_index(
        ["timestamp", "user"]
    ).unstack(
        fill_value=np.nan
    ).asfreq(
        freq="1D", fill_value=np.nan
    ).stack(future_stack=True).sort_index(level=1).reset_index()

    # forward fill monthly revision counts after the user's last active day
    df["revisions"] = df.groupby("user")["revisions"].ffill(limit=period_days).fillna(0).reset_index(drop=True).astype(int)

    return df


def race(db, output_filename):
    logger.info("Fetching data from the SQL database")
    all_revs = fetch_revisions(db)

    logger.info("Computing Arch Wiki Race data")
    rolling_revs = get_rolling_revisions(all_revs)

    # prune users that will not appear in the visualization
    max_bars = 10
    # start only after 30 days or more
    start_date = rolling_revs["timestamp"].min() + datetime.timedelta(days=30)
    pruned_revs = prune_rolling_data(rolling_revs, nlargest=max_bars, start_date=start_date)

    # fill all timestamps
    pruned_revs = fill_timestamps(pruned_revs)

    # pivot data for bcr
    df = pruned_revs.pivot(index="timestamp", columns="user", values="revisions")

    # prepare total edit counts and callback function for bcr
    # (We take the maximum revid instead of counting because some revisions
    # are lost forever.)
    total_edits = all_revs.resample("1d", on="timestamp").max()["revisions"].ffill().astype(int)
    def summary(values, ranks):
        date = values.name
        value = total_edits[date]
        s = f"Total edits: {value}"
        # the dict is passed into matplotlib.pyplot.text
        return {"x": .95, "y": .05, "s": s, "horizontalalignment": "right", "fontsize": "small"}

    # render the animation
    logger.info(f"The race is now {df.shape[0]} days long and there are {df.shape[1]} racers remaining")
    logger.info("Visualizing the Arch Wiki Race 🏁")
    bcr.bar_chart_race(
        df,
        output_filename,
        title="Arch Wiki edits in the past 30 days",
        period_summary_func=summary,
        n_bars=max_bars,
        figsize=(5, 3),
        dpi=192,
        steps_per_period=5,  # frames per period
        period_length=100,  # ms per period
    )


if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser()
    Database.set_argparser(argparser)

    args = ws.config.parse_args(argparser)

    db = Database.from_argparser(args)

    race(db, "arch-wiki-race.mp4")
