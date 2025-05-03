from pathlib import Path

import sqlalchemy as sa

from tests.fixtures.mediawiki import MediaWikiFixtureInstance


def test_compose_yaml(docker_compose_file: str) -> None:
    assert Path(docker_compose_file).is_file()


def test_mediawiki_service(mediawiki_service: str) -> None:
    assert mediawiki_service


def test_mediawiki_database_url(
    containers_dotenv_values: dict[str, str | None],
    mediawiki_database_url: sa.URL,
) -> None:
    user = containers_dotenv_values.get("MW_DB_USER")
    assert user

    engine = sa.create_engine(mediawiki_database_url)
    with engine.connect() as conn:
        # basic connectivity check
        conn.execute(sa.text("SELECT 1"))

        # ensure that the postgres user is a superuser
        value = conn.execute(
            sa.text(f"SELECT rolsuper FROM pg_roles WHERE rolname = '{user}'")
        )
        assert value.scalar_one() is True


def test_mw_api(mediawiki: MediaWikiFixtureInstance) -> None:
    api = mediawiki.api
    assert api.user.is_loggedin
    assert "sysop" in api.user.groups

    expected_rights = {
        "applychangetags",
        "createpage",
        "createtalk",
        "writeapi",
        "apihighlimits",
        "noratelimit",
        "interwiki",
        "delete",
        "bigdelete",
        "deleterevision",
        "deletelogentry",
        "deletedhistory",
        "deletedtext",
        "browsearchive",
        "mergehistory",
        "autopatrol",
        "patrol",
    }
    # pytest's assertion does not show diff for subset checks...
    for right in expected_rights:
        assert right in api.user.rights


def test_mw_db(mediawiki: MediaWikiFixtureInstance) -> None:
    db_engine = mediawiki.db_engine
    metadata = sa.MetaData()
    metadata.reflect(bind=db_engine)
    conn = db_engine.connect()

    assert "user" in metadata.tables
    t_user = metadata.tables["user"]
    s = sa.select(t_user.c.user_id, t_user.c.user_name)
    result = conn.execute(s)
    users = set()
    for u in result:
        users.add(tuple(u))

    # get the user connected to the API
    my_id = mediawiki.api.user.id
    my_name = mediawiki.api.user.name

    # The MediaWiki installer does not seem to create the Anonymous user for postgres anymore...
    # assert users == {(0, "Anonymous"), (my_id, my_name)}
    assert users == {(my_id, my_name), (my_id + 1, "MediaWiki default")}
