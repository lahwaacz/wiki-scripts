#! /usr/bin/env python3

def test_db_create(db):
    tables = set(db.metadata.tables)
    assert tables == {"archive", "category", "page", "page_props", "page_restrictions", "protected_titles", "redirect", "revision", "text"}
