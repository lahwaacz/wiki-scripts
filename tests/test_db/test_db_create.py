#! /usr/bin/env python3

custom_tables = {"namespace", "namespace_name", "ws_sync"}
users_tables = {"user", "user_groups", "ipblocks"}
pages_tables = {"archive", "category", "page", "page_props", "page_restrictions", "protected_titles", "redirect", "revision", "text"}
all_tables = custom_tables | users_tables | pages_tables

def test_db_create(db):
    tables = set(db.metadata.tables)
    assert tables == all_tables
