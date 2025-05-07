from ws.db.database import Database

custom_tables = {
    "namespace",
    "namespace_name",
    "namespace_starname",
    "namespace_canonical",
    "ws_sync",
    "ws_domain",
    "ws_url_check",
}
site_tables = {"interwiki", "tag"}
recentchanges_tables = {
    "recentchanges",
    "logging",
    "tagged_recentchange",
    "tagged_logevent",
}
users_tables = {"user", "user_groups", "ipblocks"}
revisions_tables = {
    "archive",
    "revision",
    "text",
    "tagged_revision",
    "tagged_archived_revision",
}
pages_tables = {"page", "page_props", "page_restrictions", "protected_titles"}
recomputable_tables = {
    "categorylinks",
    "externallinks",
    "imagelinks",
    "iwlinks",
    "langlinks",
    "pagelinks",
    "redirect",
    "section",
    "templatelinks",
    "ws_parser_cache_sync",
}
all_tables = (
    custom_tables
    | site_tables
    | recentchanges_tables
    | users_tables
    | revisions_tables
    | pages_tables
    | recomputable_tables
)


def test_db_create(db: Database) -> None:
    tables = set(db.metadata.tables)
    assert tables == all_tables
