#! /usr/bin/env python3

"""
Known incompatibilities from MediaWiki schema:

- Not binary compatible, but stores the same data. Thus compatibility can be
  achieved via wiki-scripts <-> MWAPI interface, but wiki-scripts can't read
  a MediaWiki database directly. This wouldn't be possible even theoretically,
  since the database can contain serialized PHP objects etc.
- Added some custom tables.
- Enforced foreign key constraints, including namespaces stored in custom
  tables, and some check constraints.
- Columns not available via the API (e.g. user passwords) are nullable, since
  they are not part of the mirroring process. Likewise revision.rev_text_id
  is nullable so that we can sync metadata and text separately.
- Removed columns that were deprecated even in MediaWiki:
    page.page_restrictions
    archive.ar_text
    archive.ar_flags
- Reordered columns in archive table to match the revision table.
- Revamped the protected_titles table - removed unnecessary columns pt_user,
  pt_reason and pt_timestamp since the information can be found in the logging
  table. See https://phabricator.wikimedia.org/T65318#2654217 for reference.
- Boolean columns use Boolean type instead of SmallInteger as in MediaWiki.
- Unknown/invalid IDs are represented by NULL instead of 0. Except for user_id,
  where we add a dummy user with id = 0 to represent anonymous users.
- Removed default values from all timestamp columns.
- Removed silly default values - if we don't know, let's make it NULL.
- Revamped the tags tables:
    - Besides the tag name, we need to store everything that MediaWiki generates
      or stores elsewhere.
    - The change_tag table was split into tagged_recentchange, tagged_logevent,
      tagged_revision and tagged_archived_revision. Foreign keys on the other
      tables are enforced.
    - The equivalent of the tag_summary table does not exist, we can live with
      the GROUP BY queries.
- Various notes on tables used by MediaWiki, but not wiki-scripts:
    - site_stats: we don't sync the site stats because the values are
      inconsistent even in MediaWiki
    - sites, site_identifiers: as of MW 1.28, they are not visible via the API
    - job, objectcache, querycache*, transcache, updatelog: not needed for
      wiki-scripts operation
    - user_former_groups: used only to prevent user auto-promotion into groups
      from which they were already removed; not visible through the API
"""

# TODO:
# - try to normalize revision + archive

from sqlalchemy import CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index, PrimaryKeyConstraint, Table
from sqlalchemy.types import ARRAY, Boolean, DateTime, Enum, Float, Integer, Interval, SmallInteger, UnicodeText

from .sql_types import SHA1, JSONEncodedDict, MWTimestamp


def create_custom_tables(metadata):
    # Even special namespaces (with negative IDs) are included, because the recentchanges and logging tables reference them.
    # But most foreign keys should be restricted to non-negative values using a CHECK constraint.
    Table("namespace", metadata,
        # can't be auto-incremented because we need to start from 0
        Column("ns_id", Integer, nullable=False, primary_key=True, autoincrement=False),
        Column("ns_case", Enum("first-letter", "case-sensitive", name="ns_case"),  nullable=False),
        Column("ns_content", Boolean, nullable=False, server_default="0"),
        Column("ns_subpages", Boolean, nullable=False, server_default="0"),
        Column("ns_nonincludable", Boolean, nullable=False, server_default="0"),
        Column("ns_defaultcontentmodel", UnicodeText),
        Column("ns_protection", UnicodeText)
    )

    # table for all namespace names
    namespace_name = Table("namespace_name", metadata,
        Column("nsn_id", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        # namespace prefixes are case-insensitive, just like the VARCHAR type
        Column("nsn_name", UnicodeText, nullable=False)
    )
    Index("nsn_id_name", namespace_name.c.nsn_id, namespace_name.c.nsn_name, unique=True)
    Index("nsn_name", namespace_name.c.nsn_name, unique=True)

    # table for default ("*") namespace names
    namespace_starname = Table("namespace_starname", metadata,
        Column("nss_id", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("nss_name", UnicodeText, nullable=False),
        ForeignKeyConstraint(["nss_id", "nss_name"],
                             ["namespace_name.nsn_id", "namespace_name.nsn_name"],
                             ondelete="CASCADE")
    )
    Index("ns_starname_id", namespace_starname.c.nss_id, unique=True)

    # table for canonical namespace names
    namespace_canonical = Table("namespace_canonical", metadata,
        Column("nsc_id", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("nsc_name", UnicodeText, nullable=False),
        ForeignKeyConstraint(["nsc_id", "nsc_name"],
                             ["namespace_name.nsn_id", "namespace_name.nsn_name"],
                             ondelete="CASCADE")
    )
    Index("ns_canonical_id", namespace_canonical.c.nsc_id, unique=True)

    Table("ws_sync", metadata,
        Column("wss_key", UnicodeText, nullable=False, primary_key=True),
        # timestamp of the last successful sync of the table
        Column("wss_timestamp", DateTime, nullable=False)
    )


def create_site_tables(metadata):
    # MW incompatibility: dropped the iw_wikiid column
    Table("interwiki", metadata,
        Column("iw_prefix", UnicodeText, primary_key=True, nullable=False),
        Column("iw_url", UnicodeText, nullable=False),
        Column("iw_api", UnicodeText),
        Column("iw_local", Boolean, nullable=False),
        Column("iw_trans", Boolean, nullable=False, server_default="0")
    )

    tag = Table("tag", metadata,
        Column("tag_id", Integer, primary_key=True, nullable=False),
        Column("tag_name", UnicodeText, nullable=False),
        Column("tag_displayname", UnicodeText, nullable=False),
        Column("tag_description", UnicodeText),
        Column("tag_defined", Boolean, nullable=False, server_default="1"),
        Column("tag_active", Boolean, nullable=False, server_default="1"),
        Column("tag_source", ARRAY(UnicodeText))
    )
    Index("tag_name", tag.c.tag_name, unique=True)


def create_recentchanges_tables(metadata):
    # Instead of rc_namespace,rc_title there could be a foreign key to page.page_id,
    # but recentchanges is probably intended to hold entries even if the page has
    # been deleted in the meantime.
    # We also don't set a foreign key constraint on rc_user for convenience, so that
    # recentchanges can be populated independently of other tables, which can then
    # use this for syncing.
    # MW incompatibility: removed recentchanges.rc_ip column (not visible through the API)
    recentchanges = Table("recentchanges", metadata,
        Column("rc_id", Integer, primary_key=True, nullable=False),
        Column("rc_timestamp", MWTimestamp, nullable=False),
        # fake foreign key (see note above): rc_user -> user.user_id
        Column("rc_user", Integer),
        Column("rc_user_text", UnicodeText, nullable=False),
        # recentchanges table may contain rows with rc_namespace < 0
        Column("rc_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("rc_title", UnicodeText, nullable=False),
        Column("rc_comment", UnicodeText, nullable=False),
        Column("rc_minor", Boolean, nullable=False, server_default="0"),
        Column("rc_bot", Boolean, nullable=False, server_default="0"),
        Column("rc_new", Boolean, nullable=False, server_default="0"),
        # fake foreign key (see note above): rc_cur_id -> page.page_id
        Column("rc_cur_id", Integer),
        # fake foreign key (see note above): rc_this_oldid -> revision.rev_id
        Column("rc_this_oldid", Integer),
        # fake foreign key (see note above): rc_last_oldid -> revision.rev_id
        Column("rc_last_oldid", Integer),
        # TODO: MW 1.27 added a "categorize" value, see https://www.mediawiki.org/wiki/Manual:CategoryMembershipChanges
        Column("rc_type", Enum("edit", "new", "log", "external", name="rc_type"), nullable=False),
        # MW incompatibility: nullable since it is not available via API
        Column("rc_source", UnicodeText),
        Column("rc_patrolled", Boolean, nullable=False, server_default="0"),
        Column("rc_old_len", Integer),
        Column("rc_new_len", Integer),
        # TODO: analogous to rev_deleted or log_deleted, should be Bitfield
        Column("rc_deleted", SmallInteger, nullable=False, server_default="0"),
        # fake foreign key (see note above): rc_logid -> logging.log_id
        Column("rc_logid", Integer),
        Column("rc_log_type", UnicodeText),
        Column("rc_log_action", UnicodeText),
        # MW incompatibility: In MediaWiki, log_params is a Blob which is supposed to
        # hold either LF separated list or serialized PHP array. We store a JSON
        # serialization of what the API gives us.
        Column("rc_params", JSONEncodedDict)
    )
    Index("rc_timestamp", recentchanges.c.rc_timestamp)
    Index("rc_namespace_title", recentchanges.c.rc_namespace, recentchanges.c.rc_title)
    Index("rc_cur_id", recentchanges.c.rc_cur_id)
    Index("rc_new_name_timestamp", recentchanges.c.rc_new, recentchanges.c.rc_namespace, recentchanges.c.rc_timestamp)
    Index("rc_ns_usertext", recentchanges.c.rc_namespace, recentchanges.c.rc_user_text)
    Index("rc_user_text", recentchanges.c.rc_user_text, recentchanges.c.rc_timestamp)
    Index("rc_name_type_patrolled_timestamp", recentchanges.c.rc_namespace, recentchanges.c.rc_type, recentchanges.c.rc_patrolled, recentchanges.c.rc_timestamp)

    logging = Table("logging", metadata,
        Column("log_id", Integer, primary_key=True, nullable=False),
        Column("log_type", UnicodeText, nullable=False),
        Column("log_action", UnicodeText, nullable=False),
        Column("log_timestamp", MWTimestamp, nullable=False),
        Column("log_user", Integer, ForeignKey("user.user_id", ondelete="SET NULL", deferrable=True, initially="DEFERRED")),
        Column("log_user_text", UnicodeText, nullable=False),
        # logging table may contain rows with log_namespace < 0
        Column("log_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("log_title", UnicodeText, nullable=False),
        # this must NOT be a FK - pages can disappear and reappear, log entries are invariant
        Column("log_page", Integer),
        Column("log_comment", UnicodeText, nullable=False),
        # MW incompatibility: In MediaWiki, log_params is a Blob which is supposed to
        # hold either LF separated list or serialized PHP array. We store a JSON
        # serialization of what the API gives us.
        Column("log_params", JSONEncodedDict, nullable=False),
        # TODO: analogous to rev_deleted, should be Bitfield
        Column("log_deleted", SmallInteger, nullable=False, server_default="0")
    )
    Index("log_type_time", logging.c.log_type, logging.c.log_timestamp)
    Index("log_user_time", logging.c.log_user, logging.c.log_timestamp)
    Index("log_page_time", logging.c.log_namespace, logging.c.log_title, logging.c.log_timestamp)
    Index("log_time", logging.c.log_timestamp)
    Index("log_user_type_time", logging.c.log_user, logging.c.log_type, logging.c.log_timestamp)
    Index("log_page_id_time", logging.c.log_page, logging.c.log_timestamp)
    Index("log_type_action", logging.c.log_type, logging.c.log_action, logging.c.log_timestamp)
    Index("log_user_text_type_time", logging.c.log_user_text, logging.c.log_type, logging.c.log_timestamp)
    Index("log_user_text_time", logging.c.log_user_text, logging.c.log_timestamp)

    Table("tagged_recentchange", metadata,
        Column("tgrc_tag_id", Integer, ForeignKey("tag.tag_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("tgrc_rc_id", Integer, ForeignKey("recentchanges.rc_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED")),
        PrimaryKeyConstraint("tgrc_tag_id", "tgrc_rc_id")
    )

    Table("tagged_logevent", metadata,
        Column("tgle_tag_id", Integer, ForeignKey("tag.tag_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("tgle_log_id", Integer, ForeignKey("logging.log_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED")),
        PrimaryKeyConstraint("tgle_tag_id", "tgle_log_id")
    )

    # TODO: create materialized views tagged_recentchange_tgname, tagged_logevent_tgname
    # (basically 'SELECT tgrc_rc_id, array_agg(tag_name) FROM tag JOIN tagged_recentchange GROUP BY tgrc_rc_id')


def create_users_tables(metadata):
    user = Table("user", metadata,
        # In MediaWiki it's 0 for anonymous edits, initialization scripts and some mass imports.
        # We'll add a dummy user with user_id == 0 before populating the table.
        Column("user_id", Integer, primary_key=True, nullable=False),
        Column("user_name", UnicodeText, nullable=False),
        Column("user_real_name", UnicodeText),
        Column("user_password", UnicodeText),
        Column("user_newpassword", UnicodeText),
        Column("user_newpass_time", MWTimestamp),
        Column("user_email", UnicodeText),
        Column("user_touched", MWTimestamp),
        Column("user_token", UnicodeText),
        Column("user_email_authenticated", MWTimestamp),
        Column("user_email_token", UnicodeText),
        Column("user_email_token_expires", MWTimestamp),
        Column("user_registration", MWTimestamp),
        Column("user_editcount", Integer),
        Column("user_password_expires", MWTimestamp)
    )
    Index("user_name", user.c.user_name, unique=True)
    Index("user_email_token", user.c.user_email_token)
    Index("user_email", user.c.user_email)

    user_groups = Table("user_groups", metadata,
        Column("ug_user", Integer, ForeignKey("user.user_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("ug_group", UnicodeText, nullable=False),
        Column("ug_expiry", MWTimestamp),
        PrimaryKeyConstraint("ug_user", "ug_group"),
        CheckConstraint("ug_user > 0", name="check_user")
    )
    Index("ug_group", user_groups.c.ug_group)
    Index("ug_expiry", user_groups.c.ug_expiry)

    ipblocks = Table("ipblocks", metadata,
        Column("ipb_id", Integer, primary_key=True, nullable=False),
        Column("ipb_address", UnicodeText, nullable=False),
        Column("ipb_user", Integer, ForeignKey("user.user_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED")),
        Column("ipb_by", Integer, ForeignKey("user.user_id", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("ipb_by_text", UnicodeText, nullable=False, server_default=""),
        Column("ipb_reason", UnicodeText, nullable=False),
        Column("ipb_timestamp", MWTimestamp, nullable=False),
        Column("ipb_auto", Boolean, nullable=False, server_default="0"),
        Column("ipb_anon_only", Boolean, nullable=False, server_default="0"),
        Column("ipb_create_account", Boolean, nullable=False, server_default="1"),
        Column("ipb_enable_autoblock", Boolean, nullable=False, server_default="1"),
        Column("ipb_expiry", MWTimestamp, nullable=False),
        # MW incompatibility: set to nullable, although they're not nullable in MW
        # (but that's a bug, even reported somewhere)
        Column("ipb_range_start", UnicodeText),
        Column("ipb_range_end", UnicodeText),
        Column("ipb_deleted", Boolean, nullable=False, server_default="0"),
        Column("ipb_block_email", Boolean, nullable=False, server_default="0"),
        Column("ipb_allow_usertalk", Boolean, nullable=False, server_default="0"),
        Column("ipb_parent_block_id", Integer, ForeignKey("ipblocks.ipb_id", ondelete="SET NULL", deferrable=True, initially="DEFERRED")),
        CheckConstraint("ipb_user > 0", name="check_user")
    )
    Index("ipb_address", ipblocks.c.ipb_address, ipblocks.c.ipb_user, ipblocks.c.ipb_auto, ipblocks.c.ipb_anon_only, unique=True)
    Index("ipb_user", ipblocks.c.ipb_user)
    Index("ipb_range", ipblocks.c.ipb_range_start, ipblocks.c.ipb_range_end)
    Index("ipb_timestamp", ipblocks.c.ipb_timestamp)
    Index("ipb_expiry", ipblocks.c.ipb_expiry)
    Index("ipb_parent_block_id", ipblocks.c.ipb_parent_block_id)

    # TODO: prepared for a custom watchlist browser
#    watchlist = Table("watchlist", metadata,
#        Column("wl_id", Integer, primary_key=True, nullable=False),
#        Column("wl_user", Integer, ForeignKey("user.user_id"), nullable=False),
#        # not a FK to page.page_id, because delete+undelete should not remove entries from the watchlist
#        Column("wl_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
#        Column("wl_title", UnicodeText, nullable=False),
#        Column("wl_notificationtimestamp", MWTimestamp),
#        CheckConstraint("wl_namespace >= 0", name="check_namespace")
#    )
#    Index("wl_user", watchlist.c.wl_user, watchlist.c.wl_namespace, watchlist.c.wl_title, unique=True)
#    Index("wl_namespace_title", watchlist.c.wl_namespace, watchlist.c.wl_title)
#    Index("wl_user_notificationtimestamp", watchlist.c.wl_user, watchlist.c.wl_notificationtimestamp)


def create_revisions_tables(metadata):
    # MW incompatibility:
    # - removed ar_text, ar_flags columns
    # - reordered columns to match the revision table
    archive = Table("archive", metadata,
        Column("ar_id", Integer, nullable=False, primary_key=True),
        # for preserving page.page_namespace and page.page_title (the corresponding row in
        # the page table is deleted, all other columns can be recomputed when undeleting)
        Column("ar_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("ar_title", UnicodeText, nullable=False),
        # for preserving revision.rev_id
        Column("ar_rev_id", Integer, nullable=False),
        # like revision.rev_page, but nullable because pages deleted prior to MW 1.11 have NULL
        # (not a FK because archived pages don't exist in page)
        # NOTE: not visible via MW API
        Column("ar_page_id", Integer),
        Column("ar_text_id", Integer, ForeignKey("text.old_id", ondelete="SET NULL", deferrable=True, initially="DEFERRED")),
        Column("ar_comment", UnicodeText, nullable=False),
        Column("ar_user", Integer, ForeignKey("user.user_id", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("ar_user_text", UnicodeText, nullable=False),
        Column("ar_timestamp", MWTimestamp, nullable=False),
        Column("ar_minor_edit", Boolean, nullable=False, server_default="0"),
        # TODO: analogous to rev_deleted, should be Bitfield
        Column("ar_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("ar_len", Integer),
        Column("ar_parent_id", Integer),
        Column("ar_sha1", SHA1),
        Column("ar_content_model", UnicodeText),
        Column("ar_content_format", UnicodeText),
        CheckConstraint("ar_namespace >= 0", name="check_namespace")
    )
    Index("ar_name_title_timestamp", archive.c.ar_namespace, archive.c.ar_title, archive.c.ar_timestamp)
    Index("ar_usertext_timestamp", archive.c.ar_user_text, archive.c.ar_timestamp)
    Index("ar_revid", archive.c.ar_rev_id, unique=True)

    revision = Table("revision", metadata,
        Column("rev_id", Integer, primary_key=True, nullable=False),
        Column("rev_page", Integer, ForeignKey("page.page_id", deferrable=True, initially="DEFERRED"), nullable=False),
        # MW incompatibility: set as nullable so that we can sync metadata and text separately
        Column("rev_text_id", Integer, ForeignKey("text.old_id", ondelete="SET NULL", deferrable=True, initially="DEFERRED")),
        Column("rev_comment", UnicodeText, nullable=False),
        Column("rev_user", Integer, ForeignKey("user.user_id", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("rev_user_text", UnicodeText, nullable=False),
        Column("rev_timestamp", MWTimestamp, nullable=False),
        Column("rev_minor_edit", Boolean, nullable=False, server_default="0"),
        # TODO: analogous to log_deleted, should be Bitfield
        Column("rev_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("rev_len", Integer),
        # FIXME: should be set as FK, but that probably breaks archiving
#        Column("rev_parent_id", Integer, ForeignKey("revision.rev_id", ondelete="SET NULL")),
        Column("rev_parent_id", Integer),
        Column("rev_sha1", SHA1),
        Column("rev_content_model", UnicodeText),
        Column("rev_content_format", UnicodeText),
    )
    Index("rev_page_id", revision.c.rev_page, revision.c.rev_id, unique=True)
    Index("rev_timestamp", revision.c.rev_timestamp)
    Index("rev_page_timestamp", revision.c.rev_page, revision.c.rev_timestamp)
    Index("rev_user_timestamp", revision.c.rev_user, revision.c.rev_timestamp)
    Index("rev_usertext_timestamp", revision.c.rev_user_text, revision.c.rev_timestamp)
    Index("rev_page_user_timestamp", revision.c.rev_page, revision.c.rev_user, revision.c.rev_timestamp)

    Table("text", metadata,
        Column("old_id", Integer, primary_key=True, nullable=False),
        Column("old_text", UnicodeText, nullable=False),
        # MW incompatibility: there is no old_flags column because it is useless for us
        # (everything is utf-8, compression is done transparently by PostgreSQL, PHP
        # objects are not supported and we will never support external storage)
    )

    Table("tagged_revision", metadata,
        Column("tgrev_tag_id", Integer, ForeignKey("tag.tag_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("tgrev_rev_id", Integer, ForeignKey("revision.rev_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED")),
        PrimaryKeyConstraint("tgrev_tag_id", "tgrev_rev_id")
    )

    Table("tagged_archived_revision", metadata,
        Column("tgar_tag_id", Integer, ForeignKey("tag.tag_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("tgar_rev_id", Integer, ForeignKey("archive.ar_rev_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED")),
        PrimaryKeyConstraint("tgar_tag_id", "tgar_rev_id")
    )

    # TODO: create materialized views tagged_revision_tgname, tagged_archived_revision_tgname
    # (basically 'SELECT tgrev_rev_id, array_agg(tag_name) FROM tag JOIN tagged_revision GROUP BY tgrev_rev_id')


def create_pages_tables(metadata):
    # MW incompatibility: removed page.page_restrictions column (unused since MW 1.9)
    # MW incompatibility: removed page.page_random column (useless for clients)
    page = Table("page", metadata,
        Column("page_id", Integer, primary_key=True, nullable=False),
        Column("page_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("page_title", UnicodeText, nullable=False),
        Column("page_is_redirect", Boolean, nullable=False, server_default="0"),
        Column("page_is_new", Boolean, nullable=False, server_default="0"),
        Column("page_touched", MWTimestamp, nullable=False),
        Column("page_links_updated", MWTimestamp),
        # FIXME: MW defect: key to revision.rev_id, breaks relationship
        Column("page_latest", Integer, nullable=False),
        Column("page_len", Integer, nullable=False),
        Column("page_content_model", UnicodeText),
        Column("page_lang", UnicodeText),
        CheckConstraint("page_namespace >= 0", name="check_namespace")
    )
    Index("page_namespace_title", page.c.page_namespace, page.c.page_title, unique=True)
    Index("page_len", page.c.page_len)
    Index("page_redirect_namespace_len", page.c.page_is_redirect, page.c.page_namespace, page.c.page_len)

    page_props = Table("page_props", metadata,
        Column("pp_page", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("pp_propname", UnicodeText, nullable=False),
        Column("pp_value", UnicodeText, nullable=False),
        Column("pp_sortkey", Float)
    )
    Index("pp_page_propname", page_props.c.pp_page, page_props.c.pp_propname, unique=True)
    Index("pp_propname_page", page_props.c.pp_propname, page_props.c.pp_page, unique=True)
    Index("pp_propname_sortkey_page", page_props.c.pp_propname, page_props.c.pp_sortkey, page_props.c.pp_page, unique=True)

    page_restrictions = Table("page_restrictions", metadata,
        Column("pr_id", Integer, primary_key=True, nullable=False),
        Column("pr_page", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("pr_type", UnicodeText, nullable=False),
        Column("pr_level", UnicodeText, nullable=False),
        Column("pr_cascade", Boolean, nullable=False),
        # unused even in MW, reserved for the future
        Column("pr_user", Integer),
        Column("pr_expiry", MWTimestamp)
    )
    Index("pr_page_type", page_restrictions.c.pr_page, page_restrictions.c.pr_type, unique=True)
    Index("pr_type_level", page_restrictions.c.pr_type, page_restrictions.c.pr_level)
    Index("pr_level", page_restrictions.c.pr_level)
    Index("pr_cascade", page_restrictions.c.pr_cascade)

    # MW incompatibility: removed unnecessary columns pt_user, pt_reason, pt_timestamp
    #    (see: https://phabricator.wikimedia.org/T65318#2654217 )
    # MW incompatibility: renamed pt_create_perm column to pt_level, moved above pt_expiry
    #    (cf. page_restrictions.pr_level)
    protected_titles = Table("protected_titles", metadata,
        Column("pt_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("pt_title", UnicodeText, nullable=False),
        Column("pt_level", UnicodeText, nullable=False),
        Column("pt_expiry", MWTimestamp, nullable=False),
        CheckConstraint("pt_namespace >= 0", name="check_namespace")
    )
    Index("pt_namespace_title", protected_titles.c.pt_namespace, protected_titles.c.pt_title, unique=True)


def create_recomputable_tables(metadata):
    # tracks page-to-page links within the wiki (e.g. [[Page name]])
    Table("pagelinks", metadata,
        Column("pl_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # MW incompatibility: removed useless pl_from_namespace column
        Column("pl_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("pl_title", UnicodeText, nullable=False),
        PrimaryKeyConstraint("pl_from", "pl_namespace", "pl_title"),
        CheckConstraint("pl_namespace >= 0", name="check_namespace"),
    )

    # tracks page transclusions (e.g. {{Page name}})
    Table("templatelinks", metadata,
        Column("tl_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # MW incompatibility: removed useless tl_from_namespace column
        Column("tl_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("tl_title", UnicodeText, nullable=False),
        PrimaryKeyConstraint("tl_from", "tl_namespace", "tl_title"),
        CheckConstraint("tl_namespace >= 0", name="check_namespace")
    )

    # tracks links to images/files used inline (e.g. [[File:Name]])
    Table("imagelinks", metadata,
        Column("il_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # MW incompatibility: removed useless il_from_namespace column
        # il_to is the target file name (and also a page title in the "File:" namespace, i.e. the namespace ID is 6)
        Column("il_to", UnicodeText, nullable=False),
        PrimaryKeyConstraint("il_from", "il_to"),
    )

    # tracks category membership (e.g. [[Category:Name]])
    Table("categorylinks", metadata,
        # cl_from is the page ID of the member page
        Column("cl_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # cl_to is the category name (and also a page title in the "Category:" namespace, i.e. the namespace ID is 14)
        Column("cl_to", UnicodeText, nullable=False),
        # the automatic sortkey (combines the cl_from page title and cl_sortkey_prefix)
        Column("cl_sortkey", UnicodeText, nullable=False),
        # the user-specified sortkey prefix, i.e. [[Category:Name|<cl_sortkey_prefix>]]
        Column("cl_sortkey_prefix", UnicodeText, nullable=False),
        # MW incompatibility: removed cl_timestamp column which is not used as of MediaWiki 1.31
        Column("cl_collation", UnicodeText, nullable=False, server_default=""),
        Column("cl_type", Enum("page", "subcat", "file", name="cl_type"), nullable=False, server_default="page"),
        PrimaryKeyConstraint("cl_from", "cl_to"),
    )

    # tracks interlanguage links (e.g. [[en:Page name]])
    langlinks = Table("langlinks", metadata,
        Column("ll_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("ll_lang", UnicodeText, ForeignKey("interwiki.iw_prefix", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # title of the target, including namespace
        Column("ll_title", UnicodeText, nullable=False),
        PrimaryKeyConstraint("ll_from", "ll_lang"),
    )
    Index("il_lang_title", langlinks.c.ll_lang, langlinks.c.ll_title)

    # tracks interwiki links (e.g. [[Wikipedia:Page name]])
    iwlinks = Table("iwlinks", metadata,
        Column("iwl_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("iwl_prefix", UnicodeText, ForeignKey("interwiki.iw_prefix", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # title of the target, including namespace
        Column("iwl_title", UnicodeText, nullable=False),
        PrimaryKeyConstraint("iwl_from", "iwl_prefix", "iwl_title"),
    )
    Index("iwl_prefix_title_from", iwlinks.c.iwl_prefix, iwlinks.c.iwl_title, iwlinks.c.iwl_from)
    Index("iwl_prefix_from_title", iwlinks.c.iwl_prefix, iwlinks.c.iwl_from, iwlinks.c.iwl_title)

    # tracks links to external URLs
    Table("externallinks", metadata,
        Column("el_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        Column("el_to", UnicodeText, nullable=False),
        PrimaryKeyConstraint("el_from", "el_to"),
    )

    # tracks targets of redirect pages
    redirect = Table("redirect", metadata,
        Column("rd_from", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), primary_key=True, nullable=False),
        # we set rd_namespace to NULL for interwiki redirects; redirects to the Special: and Media: namespaces may be tracked as well
        Column("rd_namespace", Integer, ForeignKey("namespace.ns_id")),
        Column("rd_title", UnicodeText, nullable=False),
        Column("rd_interwiki", UnicodeText, ForeignKey("interwiki.iw_prefix")),
        Column("rd_fragment", UnicodeText),
    )
    Index("rd_namespace_title_from", redirect.c.rd_namespace, redirect.c.rd_title, redirect.c.rd_from)

    # custom table tracking current page sections
    section = Table("section", metadata,
        Column("sec_page", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False),
        # section number, starting from 1 (so that "section 0" can be the text between the page title and "section 1")
        Column("sec_number", Integer, nullable=False),
        # section level, as an integer between 1 and 6, inclusive
        Column("sec_level", Integer, nullable=False),
        # section title, exactly as used in the wikicode (only whitespace is stripped)
        Column("sec_title", UnicodeText, nullable=False),
        # section anchor, dot-encoded
        Column("sec_anchor", UnicodeText, nullable=False),
        PrimaryKeyConstraint("sec_page", "sec_number"),
        CheckConstraint("sec_number > 0", name="check_sec_number"),
        CheckConstraint("sec_level >= 1 and sec_level <= 6", name="check_sec_level"),
    )
    Index("sec_page_anchor", section.c.sec_page, section.c.sec_anchor, unique=True)

    # custom table tracking which page revision is currently in the parser cache
    # (used for invalidation of entries in the parser cache)
    Table("ws_parser_cache_sync", metadata,
        Column("wspc_page_id", Integer, ForeignKey("page.page_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), primary_key=True, nullable=False),
        # the revision ID currently in the parser cache
        Column("wspc_rev_id", Integer, ForeignKey("revision.rev_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"), nullable=False)
    )

    # custom table for tracking the status of external domains
    ws_domain = Table("ws_domain", metadata,
        # domain name
        Column("name", UnicodeText, nullable=False, primary_key=True),
        # timestamp of the last check
        Column("last_check", DateTime),
        # flag indicating if the domain has been resolved at the time of the check
        Column("resolved", Boolean),
        # value of the "Server" response header
        Column("server", UnicodeText),
        # record of the SSLError exception if it occurred during the check
        Column("ssl_error", UnicodeText),
        CheckConstraint("resolved or ssl_error is null", name="check_ssl_error_implies_resolved"),
    )
    Index("ws_dom_last_check", ws_domain.c.last_check)
    Index("ws_dom_resolved_ssl_error", ws_domain.c.resolved, ws_domain.c.ssl_error)

    # custom table for tracking the status of URL checks
    ws_url_check = Table("ws_url_check", metadata,
        Column("domain_name", UnicodeText, ForeignKey("ws_domain.name"), nullable=False),
        Column("url", UnicodeText, nullable=False, primary_key=True),
        Column("last_check", DateTime),
        Column("check_duration", Interval),
        Column("http_status", Integer),        # can be null if text_status is not null
        Column("text_status", UnicodeText),    # for "connection error", "too many redirects", "CloudFlare CAPTCHA", etc.
        Column("result", UnicodeText),         # result of the check: "ok", "bad", or "needs user check"
        CheckConstraint("position('://' || domain_name in url) > 0", name="check_wsuc_domain_in_url"),
    )
    Index("wsuc_domain_name", ws_url_check.c.domain_name)
    Index("wsuc_last_check", ws_url_check.c.last_check)
    Index("wsuc_status", ws_url_check.c.http_status, ws_url_check.c.text_status)


def create_multimedia_tables(metadata):
    image = Table("image", metadata,
        Column("img_name", UnicodeText, nullable=False, primary_key=True),
        Column("img_size", Integer, nullable=False),
        Column("img_width", Integer, nullable=False),
        Column("img_height", Integer, nullable=False),
        Column("img_metadata", UnicodeText, nullable=False, server_default=""),
        Column("img_bits", Integer, nullable=False),
        Column("img_media_type", Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE")),
        Column("img_major_mime", Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), nullable=False, server_default="unknown"),
        Column("img_minor_mime", UnicodeText, nullable=False, server_default="unknown"),
        Column("img_description", UnicodeText, nullable=False),
        Column("img_user", Integer, ForeignKey("user.user_id"), nullable=False),
        Column("img_user_text", UnicodeText, nullable=False),
        Column("img_timestamp", MWTimestamp, nullable=False),
        Column("img_sha1", SHA1)
    )
    Index("img_usertext_timestamp", image.c.img_user_text, image.c.img_timestamp)
    Index("img_size", image.c.img_size)
    Index("img_timestamp", image.c.img_timestamp)
    Index("img_sha1", image.c.img_sha1)
    Index("img_media_mime", image.c.img_media_type, image.c.img_major_mime, image.c.img_minor_mime)

    oldimage = Table("oldimage", metadata,
        Column("oi_name", UnicodeText, nullable=False),
        Column("oi_archive_name", UnicodeText, nullable=False),
        Column("oi_size", Integer, nullable=False),
        Column("oi_width", Integer, nullable=False),
        Column("oi_height", Integer, nullable=False),
        Column("oi_bits", Integer, nullable=False),
        Column("oi_description", UnicodeText, nullable=False),
        Column("oi_user", Integer, ForeignKey("user.user_id"), nullable=False),
        Column("oi_user_text", UnicodeText, nullable=False),
        Column("oi_timestamp", MWTimestamp, nullable=False),
        Column("oi_metadata", UnicodeText, nullable=False, server_default=""),
        Column("oi_media_type", Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE")),
        Column("oi_major_mime", Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), nullable=False, server_default="unknown"),
        Column("oi_minor_mime", UnicodeText, nullable=False, server_default="unknown"),
        Column("oi_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("oi_sha1", SHA1)
    )
    Index("oi_usertext_timestamp", oldimage.c.oi_user_text, oldimage.c.oi_timestamp)
    Index("oi_name_timestamp", oldimage.c.oi_name, oldimage.c.oi_timestamp)
    Index("oi_name_archive_name", oldimage.c.oi_name, oldimage.c.oi_archive_name)
    Index("oi_sha1", oldimage.c.oi_sha1)

    filearchive = Table("filearchive", metadata,
        Column("fa_id", Integer, primary_key=True, nullable=False),
        Column("fa_name", UnicodeText, nullable=False),
        Column("fa_archive_name", UnicodeText),
        Column("fa_storage_group", UnicodeText),
        Column("fa_storage_key", UnicodeText),
        Column("fa_deleted_user", Integer, ForeignKey("user.user_id")),
        Column("fa_deleted_timestamp", MWTimestamp),
        Column("fa_deleted_reason", UnicodeText),
        Column("fa_size", Integer),
        Column("fa_width", Integer),
        Column("fa_height", Integer),
        Column("fa_metadata", UnicodeText, server_default=""),
        Column("fa_bits", Integer),
        Column("fa_media_type", Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE")),
        Column("fa_major_mime", Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), server_default="unknown"),
        Column("fa_minor_mime", UnicodeText, server_default="unknown"),
        Column("fa_description", UnicodeText),
        Column("fa_user", Integer, ForeignKey("user.user_id")),
        Column("fa_user_text", UnicodeText),
        Column("fa_timestamp", MWTimestamp),
        Column("fa_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("fa_sha1", SHA1)
    )
    Index("fa_name", filearchive.c.fa_name, filearchive.c.fa_timestamp)
    Index("fa_storage_group", filearchive.c.fa_storage_group, filearchive.c.fa_storage_key)
    Index("fa_deleted_timestamp", filearchive.c.fa_deleted_timestamp)
    Index("fa_user_timestamp", filearchive.c.fa_user_text, filearchive.c.fa_timestamp)
    Index("fa_sha1", filearchive.c.fa_sha1)

    # TODO: uploadstash table


def create_tables(metadata):
    create_custom_tables(metadata)
    create_site_tables(metadata)
    create_recentchanges_tables(metadata)
    create_users_tables(metadata)
    create_revisions_tables(metadata)
    create_pages_tables(metadata)
    create_recomputable_tables(metadata)
