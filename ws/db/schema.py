#! /usr/bin/env python3

"""
Known incompatibilities from MediaWiki schema:

- Not binary compatible, but stores the same data. Thus compatibility can be
  achieved via wiki-scripts <-> MWAPI interface, but wiki-scripts can't read
  a MediaWiki database directly. This wouldn't be possible even theoretically,
  since the database can contain serialized PHP objects etc.
- Added some custom tables.
- Enforced foreign key constraints (not present in MediaWiki's MySQL schema).
- Columns not available via the API (e.g. user passwords) are nullable, since
  they are not part of the mirroring process. Likewise revision.rev_text_id
  is nullable so that we can sync metadata and text separately.
- user_groups table has primary key to avoid duplicate entries.
- Removed columns that were deprecated even in MediaWiki:
    page.page_restrictions
    archive.ar_text
    archive.ar_flags
- Reordered columns in archive table to match the revision table.
- Revamped the protected_titles table - removed unnecessary columns pt_user,
  pt_reason and pt_timestamp since the information can be found in the logging
  table. See https://phabricator.wikimedia.org/T65318#2654217 for reference.
- Boolean columns use Boolean type instead of SmallInteger as in MediaWiki.
- Unknown/invalid IDs are represented by NULL instead of 0.
"""

# TODO:
# - most foreign keys are nullable in MW's PostgreSQL schema and have an ON DELETE clause
# - some non-nullable columns have silly default values - if we don't know, let's make it NULL

from sqlalchemy import \
        Table, Column, ForeignKey, Index, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.types import \
        Boolean, SmallInteger, Integer, BigInteger, Float, \
        Unicode, UnicodeText, Enum, DateTime
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from .sql_types import \
        TinyBlob, Blob, MediumBlob, UnicodeBinary, \
        MWTimestamp, Base36, JSONEncodedDict


def create_custom_tables(metadata, charset):
    # FIXME: even special namespaces (with negative IDs) are currently included, but most foreign keys should be restricted to non-negative values
    namespace = Table("namespace", metadata,
        # can't be auto-incremented because we need to start from 0
        Column("ns_id", Integer, nullable=False, primary_key=True, autoincrement=False),
        Column("ns_case", Enum("first-letter", "case-sensitive", name="ns_case"),  nullable=False),
        Column("ns_content", Boolean, nullable=False, server_default="0"),
        Column("ns_subpages", Boolean, nullable=False, server_default="0"),
        Column("ns_nonincludable", Boolean, nullable=False, server_default="0"),
        Column("ns_defaultcontentmodel", UnicodeBinary(32), server_default=None)
    )

    # table for all namespace names
    namespace_name = Table("namespace_name", metadata,
        Column("nsn_id", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        # namespace prefixes are case-insensitive, just like the VARCHAR type
        Column("nsn_name", Unicode(32), nullable=False)
    )
    Index("nsn_id_name", namespace_name.c.nsn_id, namespace_name.c.nsn_name, unique=True)
    Index("nsn_name", namespace_name.c.nsn_name, unique=True)

    # table for default ("*") namespace names
    namespace_starname = Table("namespace_starname", metadata,
        Column("nss_id", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("nss_name", Unicode(32), nullable=False),
        ForeignKeyConstraint(["nss_id", "nss_name"],
                             ["namespace_name.nsn_id", "namespace_name.nsn_name"],
                             ondelete="CASCADE")
    )
    Index("ns_starname_id", namespace_starname.c.nss_id, unique=True)

    # table for canonical namespace names
    namespace_canonical = Table("namespace_canonical", metadata,
        Column("nsc_id", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("nsc_name", Unicode(32), nullable=False),
        ForeignKeyConstraint(["nsc_id", "nsc_name"],
                             ["namespace_name.nsn_id", "namespace_name.nsn_name"],
                             ondelete="CASCADE")
    )
    Index("ns_canonical_id", namespace_canonical.c.nsc_id, unique=True)

    ws_sync = Table("ws_sync", metadata,
        Column("wss_key", Unicode(32), nullable=False, primary_key=True),
        # timestamp of the last successful sync of the table
        Column("wss_timestamp", DateTime, nullable=False)
    )


def create_users_tables(metadata, charset):
    user = Table("user", metadata,
        Column("user_id", Integer, primary_key=True, nullable=False),
        Column("user_name", UnicodeBinary(255), nullable=False, server_default=""),
        Column("user_real_name", UnicodeBinary(255), nullable=False, server_default=""),
        # MW incompatibility: set to nullable since passwords are not part of mirroring
#        Column("user_password", TinyBlob(charset=charset), nullable=False),
#        Column("user_newpassword", TinyBlob(charset=charset), nullable=False),
        Column("user_password", TinyBlob(charset=charset), server_default=None),
        Column("user_newpassword", TinyBlob(charset=charset), server_default=None),
        Column("user_newpass_time", MWTimestamp),
        # nullable for the same reason as passwords
#        Column("user_email", TinyBlob(charset=charset), nullable=False),
        Column("user_email", TinyBlob(charset=charset), server_default=None),
        Column("user_touched", MWTimestamp, nullable=False, server_default=""),
        Column("user_token", UnicodeBinary(32), nullable=False, server_default=""),
        Column("user_email_authenticated", MWTimestamp),
        Column("user_email_token", UnicodeBinary(32)),
        Column("user_email_token_expires", MWTimestamp),
        Column("user_registration", MWTimestamp),
        Column("user_editcount", Integer),
        Column("user_password_expires", MWTimestamp, server_default=None)
    )
    Index("user_name", user.c.user_name, unique=True)
    Index("user_email_token", user.c.user_email_token)
    Index("user_email", user.c.user_email, mysql_length=50)

    user_groups = Table("user_groups", metadata,
        Column("ug_user", Integer, ForeignKey("user.user_id"), nullable=False),
        Column("ug_group", UnicodeBinary(255), nullable=False),
        PrimaryKeyConstraint("ug_user", "ug_group")
    )
    Index("ug_group", user_groups.c.ug_group)

    ipblocks = Table("ipblocks", metadata,
        Column("ipb_id", Integer, primary_key=True, nullable=False),
        Column("ipb_address", TinyBlob(charset=charset), nullable=False),
        Column("ipb_user", Integer, ForeignKey("user.user_id", ondelete="CASCADE")),
        Column("ipb_by", Integer, ForeignKey("user.user_id"), nullable=False, server_default="0"),
        Column("ipb_by_text", UnicodeBinary(255), nullable=False, server_default=""),
        Column("ipb_reason", UnicodeBinary(767), nullable=False),
        Column("ipb_timestamp", MWTimestamp, nullable=False, server_default=""),
        Column("ipb_auto", Boolean, nullable=False, server_default="0"),
        Column("ipb_anon_only", Boolean, nullable=False, server_default="0"),
        Column("ipb_create_account", Boolean, nullable=False, server_default="1"),
        Column("ipb_enable_autoblock", Boolean, nullable=False, server_default="1"),
        Column("ipb_expiry", MWTimestamp, nullable=False, server_default=""),
        # MW incompatibility: set to nullable, although they're not nullable in MW
        # (but that's a bug, even reported somewhere)
        Column("ipb_range_start", TinyBlob(charset=charset)),
        Column("ipb_range_end", TinyBlob(charset=charset)),
        Column("ipb_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("ipb_block_email", Boolean, nullable=False, server_default="0"),
        Column("ipb_allow_usertalk", Boolean, nullable=False, server_default="0"),
        Column("ipb_parent_block_id", Integer, ForeignKey("ipblocks.ipb_id", ondelete="CASCADE"), server_default=None)
    )
    Index("ipb_address", ipblocks.c.ipb_address, ipblocks.c.ipb_user, ipblocks.c.ipb_auto, ipblocks.c.ipb_anon_only, mysql_length={"ipb_address": 255}, unique=True)
    Index("ipb_user", ipblocks.c.ipb_user)
    Index("ipb_range", ipblocks.c.ipb_range_start, ipblocks.c.ipb_range_end, mysql_length={"ipb_range_start": 8, "ipb_range_end": 8})
    Index("ipb_timestamp", ipblocks.c.ipb_timestamp)
    Index("ipb_expiry", ipblocks.c.ipb_expiry)
    Index("ipb_parent_block_id", ipblocks.c.ipb_parent_block_id)


def create_pages_tables(metadata, charset):
    # MW incompatibility:
    # - removed ar_text, ar_flags columns
    # - reordered columns to match the revision table
    archive = Table("archive", metadata,
        Column("ar_id", Integer, nullable=False, primary_key=True),
        # for preserving page.page_namespace and page.page_title (the corresponding row in
        # the page table is deleted, all other columns can be recomputed when undeleting)
        Column("ar_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("ar_title", UnicodeBinary(255), nullable=False),
        # for preserving revision.rev_id
        Column("ar_rev_id", Integer),
        # like revision.rev_page, but nullable because pages deleted prior to MW 1.11 have NULL
        Column("ar_page_id", Integer, ForeignKey("page.page_id")),
        Column("ar_text_id", Integer, ForeignKey("text.old_id")),
        Column("ar_comment", UnicodeBinary(767), nullable=False),
        Column("ar_user", Integer, ForeignKey("user.user_id"), nullable=False, server_default="0"),
        Column("ar_user_text", UnicodeBinary(255), nullable=False),
        Column("ar_timestamp", MWTimestamp, nullable=False, server_default=""),
        Column("ar_minor_edit", SmallInteger, nullable=False, server_default="0"),
        Column("ar_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("ar_len", Integer),
        Column("ar_parent_id", Integer, server_default=None),
        Column("ar_sha1", Base36(32), nullable=False, server_default=""),
        Column("ar_content_model", UnicodeBinary(32), server_default=None),
        Column("ar_content_format", UnicodeBinary(64), server_default=None)
    )
    Index("ar_name_title_timestamp", archive.c.ar_namespace, archive.c.ar_title, archive.c.ar_timestamp)
    Index("ar_usertext_timestamp", archive.c.ar_user_text, archive.c.ar_timestamp)
    Index("ar_revid", archive.c.ar_rev_id)

    revision = Table("revision", metadata,
        Column("rev_id", Integer, primary_key=True, nullable=False),
        # TODO: check how this works for deleted pages (MW's PostgreSQL schema has the foreign key, so it's probably OK)
        Column("rev_page", Integer, ForeignKey("page.page_id"), nullable=False),
        # MW incompatibility: set as nullable so that we can sync metadata and text separately
        Column("rev_text_id", Integer, ForeignKey("text.old_id")),
        Column("rev_comment", UnicodeBinary(767), nullable=False),
        Column("rev_user", Integer, ForeignKey("user.user_id"), nullable=False, server_default="0"),
        Column("rev_user_text", UnicodeBinary(255), nullable=False, server_default=""),
        Column("rev_timestamp", MWTimestamp, nullable=False, server_default=""),
        Column("rev_minor_edit", SmallInteger, nullable=False, server_default="0"),
        # TODO: analogous to log_deleted, should be Bitfield
        Column("rev_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("rev_len", Integer),
        # FIXME: should be set as FK, but that probably breaks archiving
#        Column("rev_parent_id", Integer, ForeignKey("revision.rev_id", ondelete="SET NULL"), server_default=None),
        Column("rev_parent_id", Integer, server_default=None),
        Column("rev_sha1", Base36(32), nullable=False, server_default=""),
        Column("rev_content_model", UnicodeBinary(32), server_default=None),
        Column("rev_content_format", UnicodeBinary(64), server_default=None),
    )
    Index("rev_page_id", revision.c.rev_page, revision.c.rev_id, unique=True)
    Index("rev_timestamp", revision.c.rev_timestamp)
    Index("rev_page_timestamp", revision.c.rev_page, revision.c.rev_timestamp)
    Index("rev_user_timestamp", revision.c.rev_user, revision.c.rev_timestamp)
    Index("rev_usertext_timestamp", revision.c.rev_user_text, revision.c.rev_timestamp)
    Index("rev_page_user_timestamp", revision.c.rev_page, revision.c.rev_user, revision.c.rev_timestamp)

    text = Table("text", metadata,
        Column("old_id", Integer, primary_key=True, nullable=False),
        Column("old_text", MediumBlob(charset=charset), nullable=False),
        Column("old_flags", TinyBlob(charset=charset), nullable=False)
    )

    # MW incompatibility: removed page.page_restrictions column (unused since MW 1.9)
    page = Table("page", metadata,
        Column("page_id", Integer, primary_key=True, nullable=False),
        Column("page_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("page_title", UnicodeBinary(255), nullable=False),
        Column("page_is_redirect", Boolean, nullable=False, server_default="0"),
        Column("page_is_new", Boolean, nullable=False, server_default="0"),
        Column("page_random", Float, nullable=False),
        Column("page_touched", MWTimestamp, nullable=False, server_default=""),
        Column("page_links_updated", MWTimestamp, server_default=None),
        # FIXME: MW defect: key to revision.rev_id, breaks relationship
        Column("page_latest", Integer, nullable=False),
        Column("page_len", Integer, nullable=False),
        Column("page_content_model", UnicodeBinary(32), server_default=None),
        Column("page_lang", UnicodeBinary(35), server_default=None)
    )
    Index("page_namespace_title", page.c.page_namespace, page.c.page_title, unique=True)
    Index("page_random", page.c.page_random)
    Index("page_len", page.c.page_len)
    Index("page_redirect_namespace_len", page.c.page_is_redirect, page.c.page_namespace, page.c.page_len)

    page_props = Table("page_props", metadata,
        Column("pp_page", Integer, ForeignKey("page.page_id", ondelete="CASCADE"), nullable=False),
        Column("pp_propname", UnicodeBinary(60), nullable=False),
        Column("pp_value", Blob(charset=charset), nullable=False),
        Column("pp_sortkey", Float, server_default=None)
    )
    Index("pp_page_propname", page_props.c.pp_page, page_props.c.pp_propname, unique=True)
    Index("pp_propname_page", page_props.c.pp_propname, page_props.c.pp_page, unique=True)
    Index("pp_propname_sortkey_page", page_props.c.pp_propname, page_props.c.pp_sortkey, page_props.c.pp_page, unique=True)

    page_restrictions = Table("page_restrictions", metadata,
        Column("pr_id", Integer, primary_key=True, nullable=False),
        Column("pr_page", Integer, ForeignKey("page.page_id", ondelete="CASCADE"), nullable=False),
        Column("pr_type", UnicodeBinary(60), nullable=False),
        Column("pr_level", UnicodeBinary(60), nullable=False),
        Column("pr_cascade", Boolean, nullable=False),
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
        Column("pt_title", UnicodeBinary(255), nullable=False),
        Column("pt_level", UnicodeBinary(60), nullable=False),
        Column("pt_expiry", MWTimestamp, nullable=False, server_default="")
    )
    Index("pt_namespace_title", protected_titles.c.pt_namespace, protected_titles.c.pt_title, unique=True)


def create_recomputable_tables(metadata, charset):
    category = Table("category", metadata,
        Column("cat_id", Integer, primary_key=True, nullable=False),
        Column("cat_title", UnicodeBinary(255), nullable=False),
        Column("cat_pages", Integer, nullable=False, server_default="0"),
        Column("cat_subcats", Integer, nullable=False, server_default="0"),
        Column("cat_files", Integer, nullable=False, server_default="0")
    )
    Index("cat_title", category.c.cat_title, unique=True)
    Index("cat_pages", category.c.cat_pages)

    redirect = Table("redirect", metadata,
        Column("rd_from", Integer, ForeignKey("page.page_id"), primary_key=True, nullable=False, server_default="0"),
        Column("rd_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("rd_title", UnicodeBinary(255), nullable=False, server_default=""),
        Column("rd_interwiki", Unicode(32), server_default=None),
        Column("rd_fragment", UnicodeBinary(255), server_default=None)
    )
    Index("rd_namespace_title_from", redirect.c.rd_namespace, redirect.c.rd_title, redirect.c.rd_from)

    pagelinks = Table("pagelinks", metadata,
        Column("pl_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        # TODO: useless, should be in view
        Column("pl_from_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("pl_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("pl_title", UnicodeBinary(255), nullable=False, server_default="")
    )

    iwlinks = Table("iwlinks", metadata,
        Column("iwl_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        Column("iwl_prefix", UnicodeBinary(20), nullable=False, server_default=""),
        Column("iwl_title", UnicodeBinary(255), nullable=False, server_default=""),
    )

    externallinks = Table("externallinks", metadata,
        Column("el_id", Integer, nullable=False, primary_key=True),
        Column("el_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        Column("el_to", Blob(charset=charset), nullable=False),
        Column("el_index", Blob(charset=charset), nullable=False)
    )

    langlinks = Table("langlinks", metadata,
        Column("ll_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        Column("ll_lang", UnicodeBinary(20), nullable=False, server_default=""),
        Column("ll_title", UnicodeBinary(255), nullable=False, server_default="")
    )

    imagelinks = Table("imagelinks", metadata,
        Column("il_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        Column("il_from_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("il_to", UnicodeBinary(255), nullable=False, server_default="")
    )

    templatelinks = Table("templatelinks", metadata,
        Column("tl_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        # TODO: useless, should be in view
        Column("tl_from_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("tl_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("tl_title", UnicodeBinary(255), nullable=False, server_default="")
    )

    categorylinks = Table("categorylinks", metadata,
        Column("cl_from", Integer, ForeignKey("page.page_id"), nullable=False, server_default="0"),
        Column("cl_to", UnicodeBinary(255), nullable=False, server_default=""),
        Column("cl_sortkey", UnicodeBinary(230), nullable=False, server_default=""),
        Column("cl_sortkey", UnicodeBinary(255), nullable=False, server_default=""),
        Column("cl_timestamp", DateTime, nullable=False),
        Column("cl_collation", UnicodeBinary(32), nullable=False, server_default=""),
        Column("cl_type", Enum("page", "subcat", "file", name="cl_type"), nullable=False, server_default="page")
    )


def create_recentchanges_tables(metadata, charset):
    # Instead of rc_namespace,rc_title there could be a foreign key to page.page_id,
    # but recentchanges is probably intended to hold entries even if the page has
    # been deleted in the meantime.
    # We also don't set a foreign key constraint on rc_user for convenience, so that
    # recentchanges can be populated independently of other tables, which can then
    # use this for syncing.
    recentchanges = Table("recentchanges", metadata,
        Column("rc_id", Integer, primary_key=True, nullable=False),
        Column("rc_timestamp", MWTimestamp, nullable=False, server_default=""),
        # fake foreign key (see note above): rc_user -> user.user_id
        # in MediaWiki it's 0 for anonymous edits, initialization scripts and some mass imports
        Column("rc_user", Integer),
        Column("rc_user_text", UnicodeBinary(255), nullable=False),
        # FIXME: can contain negative values
#        Column("rc_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("rc_namespace", Integer, nullable=False),
        Column("rc_title", UnicodeBinary(255), nullable=False, server_default=""),
        Column("rc_comment", UnicodeBinary(767), nullable=False, server_default=""),
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
        Column("rc_source", UnicodeBinary(16)),
        Column("rc_patrolled", Boolean, nullable=False, server_default="0"),
        # MW incompatibility: nullable since it is not available via API
        Column("rc_ip", UnicodeBinary(40)),
        Column("rc_old_len", Integer),
        Column("rc_new_len", Integer),
        # TODO: analogous to rev_deleted or log_deleted, should be Bitfield
        Column("rc_deleted", SmallInteger, nullable=False, server_default="0"),
        # fake foreign key (see note above): rc_logid -> logging.log_id
        Column("rc_logid", Integer),
        Column("rc_log_type", UnicodeBinary(255)),
        Column("rc_log_action", UnicodeBinary(255)),
        # MW incompatibility: In MediaWiki, log_params is a Blob which is supposed to
        # hold either LF separated list or serialized PHP array. We store a JSON
        # serialization of what the API gives us.
        Column("rc_params", JSONEncodedDict)
    )
    Index("rc_timestamp", recentchanges.c.rc_timestamp)
    Index("rc_namespace_title", recentchanges.c.rc_namespace, recentchanges.c.rc_title)
    Index("rc_cur_id", recentchanges.c.rc_cur_id)
    Index("rc_new_name_timestamp", recentchanges.c.rc_new, recentchanges.c.rc_namespace, recentchanges.c.rc_timestamp)
    Index("rc_ip", recentchanges.c.rc_ip)
    Index("rc_ns_usertext", recentchanges.c.rc_namespace, recentchanges.c.rc_user_text)
    Index("rc_user_text", recentchanges.c.rc_user_text, recentchanges.c.rc_timestamp)

    logging = Table("logging", metadata,
        Column("log_id", Integer, primary_key=True, nullable=False),
        Column("log_type", UnicodeBinary(32), nullable=False, server_default=""),
        Column("log_action", UnicodeBinary(32), nullable=False, server_default=""),
        Column("log_timestamp", MWTimestamp, nullable=False, server_default="19700101000000"),
        Column("log_user", Integer, ForeignKey("user.user_id", ondelete="SET NULL")),
        Column("log_user_text", UnicodeBinary(255), nullable=False, server_default=""),
        # FIXME: logging table may contain rows with log_namespace < 0
#        Column("log_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("log_namespace", Integer, nullable=False),
        Column("log_title", UnicodeBinary(255), nullable=False, server_default=""),
        # this must NOT be a FK - pages can disappear and reappear, log entries are invariant
        Column("log_page", Integer),
        Column("log_comment", UnicodeBinary(767), nullable=False, server_default=""),
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


def create_siteinfo_tables(metadata, charset):
    change_tag = Table("change_tag", metadata,
        Column("ct_rc_id", Integer, ForeignKey("recentchanges.rc_id", ondelete="SET NULL")),
        Column("ct_log_id", Integer, ForeignKey("logging.log_id", ondelete="CASCADE")),
        # FIXME: archiving
        Column("ct_rev_id", Integer, ForeignKey("revision.rev_id", ondelete="CASCADE")),
        Column("ct_tag", Unicode(255), nullable=False),
        Column("ct_params", Blob(charset=charset))
    )
    Index("change_tag_rc_tag", change_tag.c.ct_rc_id, change_tag.c.ct_tag, unique=True)
    Index("change_tag_log_tag", change_tag.c.ct_log_id, change_tag.c.ct_tag, unique=True)
    Index("change_tag_rev_tag", change_tag.c.ct_rev_id, change_tag.c.ct_tag, unique=True)
    Index("change_tag_tag_id", change_tag.c.ct_tag, change_tag.c.ct_rc_id, change_tag.c.change_tag.c.ct_rev_id, change_tag.c.ct_log_id)

    valid_tag = Table("valid_tag", metadata,
        Column("vt_tag", Unicode(255), primary_key=True, nullable=False)
    )

    tag_summary = Table("tag_summary", metadata,
        Column("ts_rc_id", Integer, ForeignKey("recentchanges.rc_id", ondelete="SET NULL")),
        Column("ts_log_id", Integer, ForeignKey("logging.log_id", ondelete="CASCADE")),
        # FIXME: archiving
        Column("ts_rev_id", Integer, ForeignKey("revision.rev_id", ondelete="CASCADE")),
        Column("ts_tags", MediumBlob(charset=charset), nullable=False)
    )
    Index("tag_summary_rc_id", tag_summary.c.ts_rc_id, unique=True)
    Index("tag_summary_log_id", tag_summary.c.ts_log_id, unique=True)
    Index("tag_summary_rev_id", tag_summary.c.ts_rev_id, unique=True)

    site_stats = Table("site_stats", metadata,
        Column("ss_row_id", Integer, nullable=False),
        Column("ss_total_edits", BigInteger, server_default="0"),
        Column("ss_good_articles", BigInteger, server_default="0"),
        Column("ss_total_pages", BigInteger, server_default="-1"),
        Column("ss_users", BigInteger, server_default="-1"),
        Column("ss_active_users", BigInteger, server_default="-1"),
        Column("ss_images", Integer, server_default="0")
    )

    sites = Table("sites", metadata,
        Column("site_id", Integer, nullable=False, primary_key=True),
        Column("site_global_key", UnicodeBinary(32), nullable=False),
        Column("site_type", UnicodeBinary(32), nullable=False),
        Column("site_group", UnicodeBinary(32), nullable=False),
        Column("site_source", UnicodeBinary(32), nullable=False),
        Column("site_language", UnicodeBinary(32), nullable=False),
        Column("site_protocol", UnicodeBinary(32), nullable=False),
        Column("site_domain", Unicode(255), nullable=False),
        Column("site_data", Blob(charset=charset), nullable=False),
        Column("site_forward", Boolean, nullable=False),
        Column("site_config", Blob(charset=charset), nullable=False),
    )
    Index("sites_global_key", sites.c.site_global_key, unique=True)
    Index("sites_type", sites.c.site_type)
    Index("sites_group", sites.c.site_group)
    Index("sites_source", sites.c.site_source)
    Index("sites_language", sites.c.site_language)
    Index("sites_protocol", sites.c.site_protocol)
    Index("sites_domain", sites.c.site_domain)
    Index("sites_forward", sites.c.site_forward)

    # TODO: site_identifiers table

    interwiki = Table("interwiki", metadata,
        Column("iw_prefix", Unicode(32), nullable=False),
        Column("iw_url", Blob(charset=charset), nullable=False),
        Column("iw_api", Blob(charset=charset), nullable=False),
        Column("iw_wikiid", Unicode(64), nullable=False),
        Column("iw_local", Boolean, nullable=False),
        Column("iw_trans", SmallInteger, nullable=False, server_default="0")
    )
    Index("iw_prefix", interwiki.c.iw_prefix, unique=True)

    watchlist = Table("watchlist", metadata,
        Column("wl_user", Integer, ForeignKey("user.user_id"), nullable=False),
        # FIXME: MW defect: why is there not a FK to page.page_id?
        Column("wl_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("wl_title", UnicodeBinary(255), nullable=False, server_default=""),
        Column("wl_notificationtimestamp", MWTimestamp)
    )
    Index("wl_user", watchlist.c.wl_user, watchlist.c.wl_namespace, watchlist.c.wl_title, unique=True)
    Index("wl_namespace_title", watchlist.c.wl_namespace, watchlist.c.wl_title)
    Index("wl_user_notificationtimestamp", watchlist.c.wl_user, watchlist.c.wl_notificationtimestamp)


def create_multimedia_tables(metadata, charset):
    image = Table("image", metadata,
        Column("img_name", UnicodeBinary(255), nullable=False, primary_key=True, server_default=""),
        Column("img_size", Integer, nullable=False, server_default="0"),
        Column("img_width", Integer, nullable=False, server_default="0"),
        Column("img_height", Integer, nullable=False, server_default="0"),
        Column("img_metadata", MediumBlob(charset=charset), nullable=False),
        Column("img_bits", Integer, nullable=False,
               server_default="0"),
        Column("img_media_type", Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE"), server_default=None),
        Column("img_major_mime", Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), nullable=False, server_default="unknown"),
        Column("img_minor_mime", UnicodeBinary(100), nullable=False, server_default="unknown"),
        Column("img_description", UnicodeBinary(767), nullable=False),
        Column("img_user", Integer, ForeignKey("user.user_id"), nullable=False, server_default="0"),
        Column("img_user_text", UnicodeBinary(255), nullable=False),
        Column("img_timestamp", MWTimestamp, nullable=False, server_default=""),
        Column("img_sha1", Base36(32), nullable=False, server_default="")
    )
    Index("img_usertext_timestamp", image.c.img_user_text, image.c.img_timestamp)
    Index("img_size", image.c.img_size)
    Index("img_timestamp", image.c.img_timestamp)
    Index("img_sha1", image.c.img_sha1)
    Index("img_media_mime", image.c.img_media_type, image.c.img_major_mime, image.c.img_minor_mime)

    oldimage = Table("oldimage", metadata,
        Column("oi_name", UnicodeBinary(255), nullable=False, server_default=""),
        Column("oi_archive_name", UnicodeBinary(255), nullable=False, server_default=""),
        Column("oi_size", Integer, nullable=False, server_default="0"),
        Column("oi_width", Integer, nullable=False, server_default="0"),
        Column("oi_height", Integer, nullable=False, server_default="0"),
        Column("oi_bits", Integer, nullable=False, server_default="0"),
        Column("oi_description", UnicodeBinary(767), nullable=False),
        Column("oi_user", Integer, ForeignKey("user.user_id"), nullable=False, server_default="0"),
        Column("oi_user_text", UnicodeBinary(255), nullable=False),
        Column("oi_timestamp", MWTimestamp, nullable=False, server_default=""),
        Column("oi_metadata", MediumBlob(charset=charset), nullable=False),
        Column("oi_media_type", Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE"), server_default=None),
        Column("oi_major_mime", Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), nullable=False, server_default="unknown"),
        Column("oi_minor_mime", UnicodeBinary(100), nullable=False, server_default="unknown"),
        Column("oi_deleted", SmallInteger, nullable=False, server_default="0"),
        Column("oi_sha1", Base36(32), nullable=False, server_default="")
    )
    Index("oi_usertext_timestamp", oldimage.c.oi_user_text, oldimage.c.oi_timestamp)
    Index("oi_name_timestamp", oldimage.c.oi_name, oldimage.c.oi_timestamp)
    Index("oi_name_archive_name", oldimage.c.oi_name, oldimage.c.oi_archive_name, mysql_length={"oi_archive_name": 14})
    Index("oi_sha1", oldimage.c.oi_sha1)

    filearchive = Table("filearchive", metadata,
        Column("fa_id", Integer, primary_key=True, nullable=False),
        Column("fa_name", UnicodeBinary(255), nullable=False, server_default=""),
        Column("fa_archive_name", UnicodeBinary(255), server_default=""),
        Column("fa_storage_group", UnicodeBinary(16)),
        Column("fa_storage_key", UnicodeBinary(64), server_default=""),
        Column("fa_deleted_user", Integer, ForeignKey("user.user_id")),
        Column("fa_deleted_timestamp", MWTimestamp, server_default=""),
        Column("fa_deleted_reason", UnicodeBinary(767), server_default=""),
        Column("fa_size", Integer, server_default="0"),
        Column("fa_width", Integer, server_default="0"),
        Column("fa_height", Integer, server_default="0"),
        Column("fa_metadata", MediumBlob(charset=charset)),
        Column("fa_bits", Integer, server_default="0"),
        Column("fa_media_type", Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE"), server_default=None),
        Column("fa_major_mime", Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), server_default="unknown"),
        Column("fa_minor_mime", UnicodeBinary(100), server_default="unknown"),
        Column("fa_description", UnicodeBinary(767)),
        Column("fa_user", Integer, ForeignKey("user.user_id"), server_default="0"),
        Column("fa_user_text", UnicodeBinary(255)),
        Column("fa_timestamp", MWTimestamp, server_default=""),
        Column("fa_deleted", SmallInteger, nullable=False,
               server_default="0"),
        Column("fa_sha1", Base36(32), nullable=False, server_default="")
    )
    Index("fa_name", filearchive.c.fa_name, filearchive.c.fa_timestamp)
    Index("fa_storage_group", filearchive.c.fa_storage_group, filearchive.c.fa_storage_key)
    Index("fa_deleted_timestamp", filearchive.c.fa_deleted_timestamp)
    Index("fa_user_timestamp", filearchive.c.fa_user_text, filearchive.c.fa_timestamp)
    Index("fa_sha1", filearchive.c.fa_sha1)

    # TODO: uploadstash table


def create_unused_tables(metadata, charset):
    job = Table("job", metadata,
        Column("job_id", Integer, primary_key=True, nullable=False),
        Column("job_cmd", UnicodeBinary(60), nullable=False, server_default=""),
        Column("job_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column("job_title", UnicodeBinary(255), nullable=False),
        Column("job_timestamp", MWTimestamp, server_default=None),
        Column("job_params", Blob(charset=charset), nullable=False),
        Column("job_random", Integer, nullable=False, server_default="0"),
        Column("job_attempts", Integer, nullable=False, server_default="0"),
        Column("job_token", UnicodeBinary(32), nullable=False, server_default=""),
        Column("job_token_timestamp", MWTimestamp, server_default=None),
        Column("job_sha1", Base36(32), nullable=False, server_default="")
    )

    objectcache = Table("objectcache", metadata,
        Column("keyname", UnicodeBinary(255), primary_key=True, nullable=False, server_default=""),
        Column("value", MediumBlob(charset=charset)),
        Column("exptime", DateTime)
    )

    querycache = Table("querycache", metadata,
        Column("qc_type", UnicodeBinary(32), nullable=False),
        Column("qc_value", Integer, nullable=False, server_default="0"),
        Column("qc_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("qc_title", UnicodeBinary(255), nullable=False, server_default="")
    )

    querycachetwo = Table("querycachetwo", metadata,
        Column("qcc_type", UnicodeBinary(32), nullable=False),
        Column("qcc_value", Integer, nullable=False, server_default="0"),
        Column("qcc_namespace", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("qcc_title", UnicodeBinary(255), nullable=False, server_default=""),
        Column("qcc_namespacetwo", Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default="0"),
        Column("qcc_titletwo", UnicodeBinary(255), nullable=False, server_default="")
    )

    querycache_info = Table("querycache_info", metadata,
        Column("qci_type", UnicodeBinary(32), nullable=False, server_default=""),
        Column("qci_timestamp", MWTimestamp, nullable=False, server_default="19700101000000")
    )

    searchindex = Table("searchindex", metadata,
        Column("si_page", Integer, nullable=False),
        Column("si_title", Unicode(255), nullable=False, server_default=""),
        # not binary in MediaWiki !!!
        Column("si_text", MEDIUMTEXT(charset="utf8"), nullable=False),
        mysql_engine="MyISAM"
    )

    transcache = Table("transcache", metadata,
        Column("tc_url", UnicodeBinary(255), nullable=False),
        Column("tc_contents", UnicodeText),
        Column("tc_time", MWTimestamp, nullable=False)
    )

    updatelog = Table("updatelog", metadata,
        Column("ul_key", Unicode(255), primary_key=True, nullable=False),
        Column("ul_value", Blob(charset=charset))
    )

    user_former_groups = Table("user_former_groups", metadata,
        Column("ufg_user", Integer, ForeignKey("user.user_id"), nullable=False),
        Column("ufg_group", UnicodeBinary(255), nullable=False),
        PrimaryKeyConstraint("ufg_user", "ufg_group")
    )

    # MW incompatibility: nullability + default values
    user_newtalk = Table("user_newtalk", metadata,
        Column("user_id", Integer, ForeignKey("user.user_id")),
        Column("user_ip", UnicodeBinary(40)),
        Column("user_last_timestamp", MWTimestamp, server_default=None)
    )
    Index("un_user_id", user_newtalk.c.user_id)
    Index("un_user_ip", user_newtalk.c.user_ip)


def create_tables(metadata, charset="utf8"):
    create_custom_tables(metadata, charset)
    create_users_tables(metadata, charset)
    create_pages_tables(metadata, charset)
    create_recentchanges_tables(metadata, charset)
    metadata.create_all()
