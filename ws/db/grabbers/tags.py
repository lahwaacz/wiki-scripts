#!/usr/bin/env python3

import sqlalchemy as sa

from ws.utils import value_or_none

from .GrabberBase import GrabberBase


class GrabberTags(GrabberBase):

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_tag = sa.dialects.postgresql.insert(db.tag)

        self.sql = {
            ("insert", "tag"):
                ins_tag.on_conflict_do_update(
                    index_elements=[db.tag.c.tag_name],
                    set_={
                        "tag_displayname": ins_tag.excluded.tag_displayname,
                        "tag_description": ins_tag.excluded.tag_description,
                        "tag_defined":     ins_tag.excluded.tag_defined,
                        "tag_active":      ins_tag.excluded.tag_active,
                        "tag_source":      ins_tag.excluded.tag_source,
                    }),
        }

    def gen_insert(self):
        # Tags from MW extension appear on first use, without any log event,
        # so we fetch them the same way as namespaces.
        for tag in self.api.site.tags:
            db_entry = {
                "tag_name": tag["name"],
                # as of MW 1.37, only mw-add-media and mw-remove-media have empty displayname
                "tag_displayname": tag.get("displayname", "(hidden)"),
                "tag_description": value_or_none(tag["description"]),
                "tag_defined": "defined" in tag,
                "tag_active": "active" in tag,
                "tag_source": tag["source"],
            }
            yield self.sql["insert", "tag"], db_entry

    def gen_update(self, since):
        yield from self.gen_insert()
        # TODO: delete tags that ceased to exist
