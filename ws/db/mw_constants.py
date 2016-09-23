#!/usr/bin/env python3

# all users are implicitly members of these groups
implicit_groups = {"*", "user"}

# constants for the RevisionDelete system
# https://www.mediawiki.org/wiki/Manual:RevisionDelete
# the values are stored as bitfields in the revision.rev_deleted and
# logging.log_deleted columns in the database
DELETED_TEXT = 1
DELETED_COMMENT = 2
DELETED_USER = 4
DELETED_RESTRICTED = 8

# alias (used for logs)
DELETED_ACTION = DELETED_TEXT
