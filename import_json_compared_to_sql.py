#! /usr/bin/env python3

import sys
import json
import datetime
import re

import sqlalchemy as sa

import ws.cache
from ws.db.database import Database


def migrate(revision, username_to_id):
    if set(revision.keys()) - set([
        'anon',  # optional
        'comment',
        'commenthidden',  # optional
        'minor',  # optional
        'parentid',
        'revid',
        'timestamp',
        'user',
        'userhidden',  # optional
    ]):
        raise ValueError(revision)

    try:
        userid = username_to_id[revision['user']]
    except KeyError:
        # BUG: userid for 'MediaWiki default' and several IP addresses can't be
        #      found (all anonymous edits)
        #      userid 0 doesn't seem to be in use
        #      print(0 in username_to_id.values())
        #      0 seems to be returned by getId() in User.php
        #      https://www.mediawiki.org/wiki/Manual:User.php#Other_methods
        if re.match(
            r'^(MediaWiki default|\d{1,3}(\.\d{1,3}){3})$',
            revision['user'],
        ):
            userid = 0
        # BUG: userid for 'Thayer.w' can't be found (the user may have been
        #      renamed to 'Thayer', whose userid is 3583)
        #      https://wiki.archlinux.org/api.php?action=query&list=users&ususers=Thayer
        elif revision['user'] == 'Thayer.w':
            userid = 3583
        else:
            raise

    return {
        "ar_namespace": 0,
        "ar_title": "Deleted archived revision (original title lost)",
        "ar_rev_id": revision['revid'],
        # "ar_page_id": None,
        # "ar_text_id": None,
        "ar_comment": revision['comment'],
        "ar_user": userid,
        "ar_user_text": revision['user'],
        "ar_timestamp": datetime.datetime.strptime(
            revision['timestamp'], '%Y-%m-%dT%H:%M:%S'),
        "ar_minor_edit": 'minor' in revision,
        # "ar_deleted": None,
        # "ar_len": None,
        "ar_parent_id": revision.get('parentid', 0),
        # "ar_sha1": None,
        # "ar_content_model": None,
        # "ar_content_format": None,
    }


if __name__ == '__main__':
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser()
    argparser.add_argument("compared_json_path", metavar="COMPARED_JSON_PATH")
    Database.set_argparser(argparser)
    args = argparser.parse_args()

    ws.logging.init(args)

    db = Database.from_argparser(args)

    username_to_id = {
        userprops['name']: userprops['userid']
        for userprops in db.query(list="allusers")
    }

    with open(args.compared_json_path) as revisions_stream:
        revisions_to_import = json.load(revisions_stream)

    # BUG: Nothing is currently preventing from running this script multiple
    #      times, hence multiplicating these revision records
    db.engine.execute(db.archive.insert(), [
        migrate(revision, username_to_id)
        for revision in revisions_to_import
    ])
