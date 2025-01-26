#! /usr/bin/env python3

import datetime
import json
import logging
import re

import ws.db.mw_constants as mwconst
from ws.db.database import Database

logger = logging.getLogger(__name__)


def migrate(revision, username_to_id):
    if set(revision.keys()) - set([
        'anon',  # optional
        'comment',
        'commenthidden',  # optional
        'minor',  # optional
        'parentid',
        'revid',
        'sha1hidden',  # optional
        'timestamp',
        'user',
        'userhidden',  # optional
    ]):
        raise ValueError(revision)

    username = revision['user']

    try:
        userid = username_to_id[username]
    except KeyError:
        # Anonymous edits should have userid 0
        # This includes user "MediaWiki default" and several IP addresses
        # https://www.mediawiki.org/wiki/Manual:User.php#Other_methods
        if re.match(
            r'^(MediaWiki default|\d{1,3}(\.\d{1,3}){3})$',
            username,
        ):
            if 'anon' not in revision:
                raise ValueError(revision)
            userid = 0
        # User "Thayer.w" was renamed to "Thayer" at some stage
        # Thayer's userid is 3583
        # https://wiki.archlinux.org/api.php?action=query&list=users&ususers=Thayer
        elif username == 'Thayer.w':
            username = 'Thayer'
            userid = 3583
        else:
            raise

    # prepare the ar_deleted field
    ar_deleted = 0
    if "sha1hidden" in revision:
        ar_deleted |= mwconst.DELETED_TEXT
    if "commenthidden" in revision:
        ar_deleted |= mwconst.DELETED_COMMENT
    if "userhidden" in revision:
        ar_deleted |= mwconst.DELETED_USER
    if "suppressed" in revision:
        ar_deleted |= mwconst.DELETED_RESTRICTED

    return {
        "ar_namespace": 0,
        "ar_title": "Deleted archived revision (original title lost)",
        "ar_rev_id": revision['revid'],
        # "ar_page_id": None,
        # "ar_text_id": None,
        "ar_comment": revision['comment'],
        "ar_user": userid,
        "ar_user_text": username,
        "ar_timestamp": datetime.datetime.strptime(
            revision['timestamp'], '%Y-%m-%dT%H:%M:%S'),
        "ar_minor_edit": 'minor' in revision,
        "ar_deleted": ar_deleted,
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

    logger.info("Migrating {} revisions...".format(len(revisions_to_import)))

    migrated_revisions = [
        migrate(revision, username_to_id)
        for revision in revisions_to_import
    ]

    # The ar_rev_id column has a unique constraint, which makes this script
    # idempotent (insert will fail here if the records were already imported)
    db.engine.execute(db.archive.insert(), migrated_revisions)
