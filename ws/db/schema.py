#! /usr/bin/env python3

from sqlalchemy import Table, Column, ForeignKey, Index
from sqlalchemy.types import Boolean, Integer, SmallInteger, Float, Unicode, UnicodeText, Enum
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from .sql_types import \
        TinyBlob, Blob, MediumBlob, LongBlob, UnicodeBinary, \
        MWTimestamp, Base36


def create_custom_tables(metadata, charset):
    namespace = Table('namespace', metadata,
        Column('ns_id', Integer, nullable=False, primary_key=True, autoincrement=False),
        Column('ns_case', Enum("first-letter", "case-sensitive"),  nullable=False),
        Column('ns_content', Boolean, nullable=False, server_default='0'),
        Column('ns_subpages', Boolean, nullable=False, server_default='0'),
        Column('ns_nonincludable', Boolean, nullable=False, server_default='0'),
        Column('ns_defaultcontentmodel', UnicodeBinary(32), server_default=None)
    )

    # TODO: constraints on the boolean columns
    namespace_name = Table('namespace_name', metadata,
        Column('nsn_id', Integer, ForeignKey("namespace.ns_id"), nullable=False),
        # namespace prefixes are case-insensitive, just like the VARCHAR type
        Column('nsn_name', Unicode(32), nullable=False),
        Column('nsn_starname', Boolean, nullable=False, server_default='0'),
        Column('nsn_canonical', Boolean, nullable=False, server_default='0'),
        Column('nsn_alias', Boolean, nullable=False, server_default='0')
    )
    Index("nsn_name", namespace_name.c.nsn_name, unique=True)


# TODO: most foreign keys are nullable in MW's PostgreSQL schema and have an ON DELETE clause

def create_pages_tables(metadata, charset):
    archive = Table('archive', metadata,
        Column('ar_id', Integer, nullable=False, primary_key=True),
        Column('ar_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('ar_title', UnicodeBinary(255), nullable=False, server_default=''),
        Column('ar_text', MediumBlob(charset=charset), nullable=False),
        Column('ar_comment', UnicodeBinary(767), nullable=False),
        Column('ar_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('ar_user_text', UnicodeBinary(255), nullable=False),
        Column('ar_timestamp', MWTimestamp, nullable=False, server_default=''),
        Column('ar_minor_edit', SmallInteger, nullable=False, server_default='0'),
        Column('ar_flags', TinyBlob(charset=charset), nullable=False),
        Column('ar_rev_id', Integer),
        Column('ar_text_id', Integer, ForeignKey("text.old_id")),
        Column('ar_deleted', SmallInteger, nullable=False, server_default='0'),
        Column('ar_len', Integer),
        Column('ar_page_id', Integer),
        Column('ar_parent_id', Integer, server_default=None),
        Column('ar_sha1', Base36(32), nullable=False, server_default=''),
        Column('ar_content_model', UnicodeBinary(32), server_default=None),
        Column('ar_content_format', UnicodeBinary(64), server_default=None)
    )
    Index("ar_name_title_timestamp", archive.c.ar_namespace, archive.c.ar_title, archive.c.ar_timestamp)
    Index("ar_usertext_timestamp", archive.c.ar_user_text, archive.c.ar_timestamp)
    Index("ar_revid", archive.c.ar_rev_id)

    revision = Table('revision', metadata,
        Column('rev_id', Integer, primary_key=True, nullable=False),
        # TODO: check how this works for deleted pages (MW's PostgreSQL schema has the foreign key, so it's probably OK)
        Column('rev_page', Integer, ForeignKey("page.page_id"), nullable=False),
        Column('rev_text_id', Integer, ForeignKey("text.old_id"), nullable=False),
        Column('rev_comment', UnicodeBinary(767), nullable=False),
        Column('rev_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('rev_user_text', UnicodeBinary(255), nullable=False, server_default=''),
        Column('rev_timestamp', MWTimestamp, nullable=False, server_default=''),
        Column('rev_minor_edit', SmallInteger, nullable=False, server_default='0'),
        Column('rev_deleted', SmallInteger, nullable=False, server_default='0'),
        Column('rev_len', Integer),
        Column('rev_parent_id', Integer, server_default=None),
        Column('rev_sha1', Base36(32), nullable=False, server_default=''),
        Column('rev_content_model', UnicodeBinary(32), server_default=None),
        Column('rev_content_format', UnicodeBinary(64), server_default=None),
    )
    Index("rev_page_id", revision.c.rev_page, revision.c.rev_id, unique=True)
    Index("rev_timestamp", revision.c.rev_timestamp)
    Index("rev_page_timestamp", revision.c.rev_page, revision.c.rev_timestamp)
    Index("rev_user_timestamp", revision.c.rev_user, revision.c.rev_timestamp)
    Index("rev_usertext_timestamp", revision.c.rev_user_text, revision.c.rev_timestamp)
    Index("rev_page_user_timestamp", revision.c.rev_page, revision.c.rev_user, revision.c.rev_timestamp)

    text = Table('text', metadata,
        Column('old_id', Integer, primary_key=True, nullable=False),
        Column('old_text', MediumBlob(charset=charset), nullable=False),
        Column('old_flags', TinyBlob(charset=charset), nullable=False)
    )

    page = Table('page', metadata,
        Column('page_id', Integer, primary_key=True, nullable=False),
        Column('page_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column('page_title', UnicodeBinary(255), nullable=False),
        Column('page_restrictions', TinyBlob(charset=charset), nullable=False),
        Column('page_is_redirect', SmallInteger, nullable=False, server_default='0'),
        Column('page_is_new', SmallInteger, nullable=False, server_default='0'),
        Column('page_random', Float, nullable=False),
        Column('page_touched', MWTimestamp, nullable=False, server_default=''),
        Column('page_links_updated', MWTimestamp, server_default=None),
        # FIXME: MW defect: key to revision.rev_id, breaks relationship
        Column('page_latest', Integer, nullable=False),
        Column('page_len', Integer, nullable=False),
        Column('page_content_model', UnicodeBinary(32), server_default=None),
        Column('page_lang', UnicodeBinary(35), server_default=None)
    )
    Index("page_namespace_title", page.c.page_namespace, page.c.page_title, unique=True)
    Index("page_random", page.c.page_random)
    Index("page_len", page.c.page_len)
    Index("page_redirect_namespace_len", page.c.page_is_redirect, page.c.page_namespace, page.c.page_len)

    page_props = Table('page_props', metadata,
        Column('pp_page', Integer, ForeignKey("page.page_id"), nullable=False),
        Column('pp_propname', UnicodeBinary(60), nullable=False),
        Column('pp_value', Blob(charset=charset), nullable=False),
        Column('pp_sortkey', Float, server_default=None)
    )
    Index("pp_page_propname", page_props.c.pp_page, page_props.c.pp_propname, unique=True)
    Index("pp_propname_page", page_props.c.pp_propname, page_props.c.pp_page, unique=True)
    Index("pp_propname_sortkey_page", page_props.c.pp_propname, page_props.c.pp_sortkey, page_props.c.pp_page, unique=True)

    page_restrictions = Table('page_restrictions', metadata,
        Column('pr_id', Integer, primary_key=True, nullable=False),
        Column('pr_page', Integer, ForeignKey("page.page_id"), nullable=False),
        Column('pr_type', UnicodeBinary(60), nullable=False),
        Column('pr_level', UnicodeBinary(60), nullable=False),
        Column('pr_cascade', SmallInteger, nullable=False),
        Column('pr_user', Integer),
        Column('pr_expiry', MWTimestamp)
    )
    Index("pr_page_type", page_restrictions.c.pr_page, page_restrictions.c.pr_type, unique=True)
    Index("pr_type_level", page_restrictions.c.pr_type, page_restrictions.c.pr_level)
    Index("pr_level", page_restrictions.c.pr_level)
    Index("pr_cascade", page_restrictions.c.pr_cascade)

    protected_titles = Table('protected_titles', metadata,
        Column('pt_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column('pt_title', UnicodeBinary(255), nullable=False),
        Column('pt_user', Integer, ForeignKey("user.user_id"), nullable=False),
        Column('pt_reason', UnicodeBinary(767)),
        Column('pt_timestamp', MWTimestamp, nullable=False),
        Column('pt_expiry', MWTimestamp, nullable=False, server_default=''),
        Column('pt_create_perm', UnicodeBinary(60), nullable=False)
    )
    Index("pt_namespace_title", protected_titles.c.pt_namespace, protected_titles.c.pt_title, unique=True)
    Index("pt_timestamp", protected_titles.c.pt_timestamp)

    category = Table('category', metadata,
        Column('cat_id', Integer, primary_key=True, nullable=False),
        Column('cat_title', UnicodeBinary(255), nullable=False),
        Column('cat_pages', Integer, nullable=False, server_default='0'),
        Column('cat_subcats', Integer, nullable=False, server_default='0'),
        Column('cat_files', Integer, nullable=False, server_default='0')
    )
    Index("cat_title", category.c.cat_title, unique=True)
    Index("cat_pages", category.c.cat_pages)

    redirect = Table('redirect', metadata,
        Column('rd_from', Integer, ForeignKey("page.page_id"), primary_key=True, nullable=False, server_default='0'),
        Column('rd_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('rd_title', UnicodeBinary(255), nullable=False, server_default=''),
        Column('rd_interwiki', Unicode(32), server_default=None),
        Column('rd_fragment', UnicodeBinary(255), server_default=None)
    )
    Index("rd_namespace_title_from", redirect.c.rd_namespace, redirect.c.rd_title, redirect.c.rd_from)


def create_links_tables(metadata, charset):
    pagelinks = Table('pagelinks', metadata,
        Column('pl_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        # TODO: useless, should be in view
        Column('pl_from_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('pl_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('pl_title', UnicodeBinary(255), nullable=False, server_default='')
    )

    iwlinks = Table('iwlinks', metadata,
        Column('iwl_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        Column('iwl_prefix', UnicodeBinary(20), nullable=False, server_default=''),
        Column('iwl_title', UnicodeBinary(255), nullable=False, server_default=''),
    )

    externallinks = Table('externallinks', metadata,
        Column('el_id', Integer, nullable=False, primary_key=True),
        Column('el_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        Column('el_to', Blob(charset=charset), nullable=False),
        Column('el_index', Blob(charset=charset), nullable=False)
    )

    langlinks = Table('langlinks', metadata,
        Column('ll_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        Column('ll_lang', UnicodeBinary(20), nullable=False, server_default=''),
        Column('ll_title', UnicodeBinary(255), nullable=False, server_default='')
    )

    imagelinks = Table('imagelinks', metadata,
        Column('il_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        Column('il_from_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('il_to', UnicodeBinary(255), nullable=False, server_default='')
    )

    templatelinks = Table('templatelinks', metadata,
        Column('tl_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        # TODO: useless, should be in view
        Column('tl_from_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('tl_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('tl_title', UnicodeBinary(255), nullable=False, server_default='')
    )

    categorylinks = Table('categorylinks', metadata,
        Column('cl_from', Integer, ForeignKey("page.page_id"), nullable=False, server_default='0'),
        Column('cl_to', UnicodeBinary(255), nullable=False, server_default=''),
        Column('cl_sortkey', UnicodeBinary(230), nullable=False, server_default=''),
        Column('cl_sortkey', UnicodeBinary(255), nullable=False, server_default=''),
        Column('cl_timestamp', TIMESTAMP(timezone=False), nullable=False),
        Column('cl_collation', UnicodeBinary(32), nullable=False, server_default=''),
        Column('cl_type', Enum("page", "subcat", "file"), nullable=False, server_default="page")
    )


def create_recentchanges_tables(metadata, charset):
    recentchanges = Table('recentchanges', metadata,
        Column('rc_id', Integer, primary_key=True, nullable=False),
        Column('rc_timestamp', MWTimestamp, nullable=False, server_default=''),
        Column('rc_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('rc_user_text', UnicodeBinary(255), nullable=False),
        Column('rc_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('rc_title', UnicodeBinary(255), nullable=False, server_default=''),
        Column('rc_comment', UnicodeBinary(767), nullable=False, server_default=''),
        Column('rc_minor', SmallInteger, nullable=False, server_default='0'),
        Column('rc_bot', SmallInteger, nullable=False, server_default='0'),
        Column('rc_new', SmallInteger, nullable=False, server_default='0'),
        # FK: rc_cur_id -> page.page_id     (not in PostgreSQL)
        Column('rc_cur_id', Integer, nullable=False, server_default='0'),
        # FK: rc_this_oldid -> revision.rev_id      (not in PostgreSQL)
        Column('rc_this_oldid', Integer, nullable=False, server_default='0'),
        # FK: rc_this_oldid -> revision.rev_id      (not in PostgreSQL)
        Column('rc_last_oldid', Integer, nullable=False, server_default='0'),
        Column('rc_type', SmallInteger, nullable=False, server_default='0'),
        Column('rc_source', UnicodeBinary(16), nullable=False, server_default=''),
        Column('rc_patrolled', SmallInteger, nullable=False, server_default='0'),
        Column('rc_ip', UnicodeBinary(40), nullable=False, server_default=''),
        Column('rc_old_len', Integer),
        Column('rc_new_len', Integer),
        Column('rc_deleted', SmallInteger, nullable=False, server_default='0'),
        Column('rc_logid', Integer, nullable=False, server_default='0'),
        Column('rc_log_type', UnicodeBinary(255), server_default=None),
        Column('rc_log_action', UnicodeBinary(255), server_default=None),
        Column('rc_params', Blob(charset=charset))
    )

    watchlist = Table('watchlist', metadata,
        Column('wl_user', Integer, ForeignKey("user.user_id"), nullable=False),
        # FIXME: MW defect: why is there not a FK to page.page_id?
        Column('wl_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('wl_title', UnicodeBinary(255), nullable=False, server_default=''),
        Column('wl_notificationtimestamp', MWTimestamp)
    )


def create_users_tables(metadata, charset):
    user = Table('user', metadata,
        Column('user_id', Integer, primary_key=True, nullable=False),
        Column('user_name', UnicodeBinary(255), nullable=False, server_default=''),
        Column('user_real_name', UnicodeBinary(255), nullable=False, server_default=''),
        Column('user_password', TinyBlob(charset=charset), nullable=False),
        Column('user_newpassword', TinyBlob(charset=charset), nullable=False),
        Column('user_newpass_time', MWTimestamp),
        Column('user_email', TinyBlob(charset=charset), nullable=False),
        Column('user_touched', MWTimestamp, nullable=False, server_default=''),
        Column('user_token', UnicodeBinary(32), nullable=False, server_default=''),
        Column('user_email_authenticated', MWTimestamp),
        Column('user_email_token', UnicodeBinary(32)),
        Column('user_email_token_expires', MWTimestamp),
        Column('user_registration', MWTimestamp),
        Column('user_editcount', Integer),
        Column('user_password_expires', MWTimestamp, server_default=None)
    )

    user_groups = Table('user_groups', metadata,
        Column('ug_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('ug_group', UnicodeBinary(255), nullable=False, server_default='')
    )

    ipblocks = Table('ipblocks', metadata,
        Column('ipb_id', Integer, primary_key=True, nullable=False),
        Column('ipb_address', TinyBlob(charset=charset), nullable=False),
        Column('ipb_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('ipb_by', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('ipb_by_text', UnicodeBinary(255), nullable=False, server_default=''),
        Column('ipb_reason', UnicodeBinary(767), nullable=False),
        Column('ipb_timestamp', MWTimestamp, nullable=False, server_default=''),
        Column('ipb_auto', Boolean, nullable=False, server_default='0'),
        Column('ipb_anon_only', Boolean, nullable=False, server_default='0'),
        Column('ipb_create_account', Boolean, nullable=False, server_default='1'),
        Column('ipb_enable_autoblock', Boolean, nullable=False, server_default='1'),
        Column('ipb_expiry', MWTimestamp, nullable=False, server_default=''),
        Column('ipb_range_start', TinyBlob(charset=charset), nullable=False),
        Column('ipb_range_end', TinyBlob(charset=charset), nullable=False),
        Column('ipb_deleted', Boolean, nullable=False, server_default='0'),
        Column('ipb_block_email', Boolean, nullable=False, server_default='0'),
        Column('ipb_allow_usertalk', Boolean, nullable=False, server_default='0'),
        # FIXME: MW defect: FK to the same table
        Column('ipb_parent_block_id', Integer, ForeignKey("ipblocks.ipb_id", ondelete="SET NULL"), server_default=None)
    )


def create_siteinfo_tables(metadata, charset):
    change_tag = Table('change_tag', metadata,
        Column('ct_rc_id', Integer),
        Column('ct_log_id', Integer),
        Column('ct_rev_id', Integer),
        Column('ct_tag', Unicode(255), nullable=False),
        Column('ct_params', Blob(charset=charset))
    )

    valid_tag = Table('valid_tag', metadata,
        Column('vt_tag', Unicode(255), primary_key=True, nullable=False)
    )

    tag_summary = Table('tag_summary', metadata,
        Column('ts_rc_id', Integer),
        Column('ts_log_id', Integer),
        Column('ts_rev_id', Integer),
        Column('ts_tags', MediumBlob(charset=charset), nullable=False)
    )

    logging = Table('logging', metadata,
        Column('log_id', Integer, primary_key=True, nullable=False),
        Column('log_type', UnicodeBinary(32), nullable=False, server_default=''),
        Column('log_action', UnicodeBinary(32), nullable=False, server_default=''),
        Column('log_timestamp', MWTimestamp, nullable=False, server_default='19700101000000'),
        Column('log_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('log_user_text', UnicodeBinary(255), nullable=False, server_default=''),
        Column('log_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('log_title', UnicodeBinary(255), nullable=False, server_default=''),
        Column('log_page', Integer),
        Column('log_comment', UnicodeBinary(767), nullable=False, server_default=''),
        Column('log_params', Blob(charset=charset), nullable=False),
        Column('log_deleted', SmallInteger, nullable=False,server_default='0')
    )

    # TODO: log_search table

    site_stats = Table('site_stats', metadata,
        Column('ss_row_id', Integer, nullable=False),
        Column('ss_total_edits', BigInteger, server_default='0'),
        Column('ss_good_articles', BigInteger, server_default='0'),
        Column('ss_total_pages', BigInteger, server_default='-1'),
        Column('ss_users', BigInteger, server_default='-1'),
        Column('ss_active_users', BigInteger, server_default='-1'),
        Column('ss_images', Integer, server_default='0')
    )

    sites = Table('sites', metadata,
        Column('site_id', Integer, nullable=False, primary_key=True),
        Column('site_global_key', UnicodeBinary(32), nullable=False),
        Column('site_type', UnicodeBinary(32), nullable=False),
        Column('site_group', UnicodeBinary(32), nullable=False),
        Column('site_source', UnicodeBinary(32), nullable=False),
        Column('site_language', UnicodeBinary(32), nullable=False),
        Column('site_protocol', UnicodeBinary(32), nullable=False),
        Column('site_domain', Unicode(255), nullable=False),
        Column('site_data', Blob(charset=charset), nullable=False),
        Column('site_forward', Boolean, nullable=False),
        Column('site_config', Blob(charset=charset), nullable=False),
    )

    # TODO: site_identifiers table

    interwiki = Table('interwiki', metadata,
        Column('iw_prefix', Unicode(32), nullable=False),
        Column('iw_url', Blob(charset=charset), nullable=False),
        Column('iw_api', Blob(charset=charset), nullable=False),
        Column('iw_wikiid', Unicode(64), nullable=False),
        Column('iw_local', Boolean, nullable=False),
        Column('iw_trans', SmallInteger, nullable=False, server_default='0')
    )


def create_multimedia_tables(metadata, charset):
    image = Table('image', metadata,
        Column('img_name', UnicodeBinary(255), nullable=False, primary_key=True, server_default=''),
        Column('img_size', Integer, nullable=False, server_default='0'),
        Column('img_width', Integer, nullable=False, server_default='0'),
        Column('img_height', Integer, nullable=False, server_default='0'),
        Column('img_metadata', MediumBlob(charset=charset), nullable=False),
        Column('img_bits', Integer, nullable=False,
               server_default='0'),
        Column('img_media_type', Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE"), server_default=None),
        Column('img_major_mime', Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), nullable=False, server_default='unknown'),
        Column('img_minor_mime', UnicodeBinary(100), nullable=False, server_default='unknown'),
        Column('img_description', UnicodeBinary(767), nullable=False),
        Column('img_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('img_user_text', UnicodeBinary(255), nullable=False),
        Column('img_timestamp', MWTimestamp, nullable=False, server_default=''),
        Column('img_sha1', Base36(32), nullable=False, server_default='')
    )

    oldimage = Table('oldimage', metadata,
        Column('oi_name', UnicodeBinary(255), nullable=False, server_default=''),
        Column('oi_archive_name', UnicodeBinary(255), nullable=False, server_default=''),
        Column('oi_size', Integer, nullable=False, server_default='0'),
        Column('oi_width', Integer, nullable=False, server_default='0'),
        Column('oi_height', Integer, nullable=False, server_default='0'),
        Column('oi_bits', Integer, nullable=False, server_default='0'),
        Column('oi_description', UnicodeBinary(767), nullable=False),
        Column('oi_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('oi_user_text', UnicodeBinary(255), nullable=False),
        Column('oi_timestamp', MWTimestamp, nullable=False, server_default=''),
        Column('oi_metadata', MediumBlob(charset=charset), nullable=False),
        Column('oi_media_type', Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE"), server_default=None),
        Column('oi_major_mime', Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), nullable=False, server_default='unknown'),
        Column('oi_minor_mime', UnicodeBinary(100), nullable=False, server_default='unknown'),
        Column('oi_deleted', SmallInteger, nullable=False, server_default='0'),
        Column('oi_sha1', Base36(32), nullable=False, server_default='')
    )

    filearchive = Table('filearchive', metadata,
        Column('fa_id', Integer, primary_key=True, nullable=False),
        Column('fa_name', UnicodeBinary(255), nullable=False, server_default=''),
        Column('fa_archive_name', UnicodeBinary(255), server_default=''),
        Column('fa_storage_group', UnicodeBinary(16)),
        Column('fa_storage_key', UnicodeBinary(64), server_default=''),
        Column('fa_deleted_user', Integer, ForeignKey("user.user_id")),
        Column('fa_deleted_timestamp', MWTimestamp, server_default=''),
        Column('fa_deleted_reason', UnicodeBinary(767), server_default=''),
        Column('fa_size', Integer, server_default='0'),
        Column('fa_width', Integer, server_default='0'),
        Column('fa_height', Integer, server_default='0'),
        Column('fa_metadata', MediumBlob(charset=charset)),
        Column('fa_bits', Integer, server_default='0'),
        Column('fa_media_type', Enum("UNKNOWN", "BITMAP", "DRAWING", "AUDIO", "VIDEO", "MULTIMEDIA", "OFFICE", "BLOB", "EXECUTABLE", "ARCHIVE"), server_default=None),
        Column('fa_major_mime', Enum("unknown", "application", "audio", "image", "text", "video", "message", "model", "multipart", "chemical"), server_default="unknown"),
        Column('fa_minor_mime', UnicodeBinary(100), server_default="unknown"),
        Column('fa_description', UnicodeBinary(767)),
        Column('fa_user', Integer, ForeignKey("user.user_id"), server_default='0'),
        Column('fa_user_text', UnicodeBinary(255)),
        Column('fa_timestamp', MWTimestamp, server_default=''),
        Column('fa_deleted', SmallInteger, nullable=False,
               server_default='0'),
        Column('fa_sha1', Base36(32), nullable=False, server_default='')
    )

    # TODO: uploadstash table


def create_unused_tables(metadata, charset):
    job = Table('job', metadata,
        Column('job_id', Integer, primary_key=True, nullable=False),
        Column('job_cmd', UnicodeBinary(60), nullable=False, server_default=''),
        Column('job_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False),
        Column('job_title', UnicodeBinary(255), nullable=False),
        Column('job_timestamp', MWTimestamp, server_default=None),
        Column('job_params', Blob(charset=charset), nullable=False),
        Column('job_random', Integer, nullable=False, server_default='0'),
        Column('job_attempts', Integer, nullable=False, server_default='0'),
        Column('job_token', UnicodeBinary(32), nullable=False, server_default=''),
        Column('job_token_timestamp', MWTimestamp, server_default=None),
        Column('job_sha1', Base36(32), nullable=False, server_default='')
    )

    objectcache = Table('objectcache', metadata,
        Column('keyname', UnicodeBinary(255), primary_key=True, nullable=False, server_default=''),
        Column('value', MediumBlob(charset=charset)),
        Column('exptime', DATETIME(timezone=False))
    )

    querycache = Table('querycache', metadata,
        Column('qc_type', UnicodeBinary(32), nullable=False),
        Column('qc_value', Integer, nullable=False, server_default='0'),
        Column('qc_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('qc_title', UnicodeBinary(255), nullable=False, server_default='')
    )

    querycachetwo = Table('querycachetwo', metadata,
        Column('qcc_type', UnicodeBinary(32), nullable=False),
        Column('qcc_value', Integer, nullable=False, server_default='0'),
        Column('qcc_namespace', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('qcc_title', UnicodeBinary(255), nullable=False, server_default=''),
        Column('qcc_namespacetwo', Integer, ForeignKey("namespace.ns_id"), nullable=False, server_default='0'),
        Column('qcc_titletwo', UnicodeBinary(255), nullable=False, server_default='')
    )

    querycache_info = Table('querycache_info', metadata,
        Column('qci_type', UnicodeBinary(32), nullable=False, server_default=''),
        Column('qci_timestamp', MWTimestamp, nullable=False, server_default='19700101000000')
    )

    searchindex = Table('searchindex', metadata,
        Column('si_page', Integer, nullable=False),
        Column('si_title', Unicode(255), nullable=False, server_default=''),
        # not binary in MediaWiki !!!
        Column('si_text', MEDIUMTEXT(charset="utf8"), nullable=False),
        mysql_engine="MyISAM"
    )

    transcache = Table('transcache', metadata,
        Column('tc_url', UnicodeBinary(255), nullable=False),
        Column('tc_contents', UnicodeText),
        Column('tc_time', MWTimestamp, nullable=False)
    )

    updatelog = Table('updatelog', metadata,
        Column('ul_key', Unicode(255), primary_key=True, nullable=False),
        Column('ul_value', Blob(charset=charset))
    )

    user_former_groups = Table('user_former_groups', metadata,
        Column('ufg_user', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('ufg_group', UnicodeBinary(255), nullable=False, server_default='')
    )

    user_newtalk = Table('user_newtalk', metadata,
        Column('user_id', Integer, ForeignKey("user.user_id"), nullable=False, server_default='0'),
        Column('user_ip', UnicodeBinary(40), nullable=False, server_default=''),
        Column('user_last_timestamp', MWTimestamp, server_default=None)
    )


def create_tables(metadata, charset="utf8"):
    create_custom_tables(metadata, charset)
    create_pages_tables(metadata, charset)
    create_users_tables(metadata, charset)
    metadata.create_all()
