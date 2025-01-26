#! /usr/bin/env python3

import hashlib
import json
import os.path
import re
import subprocess
import tarfile
from pprint import pprint

import pytest
import requests
import sqlalchemy as sa
from pytest_nginx import factories
from pytest_postgresql.factories import postgresql

from ws.client.api import API

from .postgresql import postgresql_proc

_mw_ver = "1.33"
_mw_rel = _mw_ver + ".1"
_mw_url = "https://releases.wikimedia.org/mediawiki/" + _mw_ver + "/mediawiki-" + _mw_rel + ".tar.gz"
_mw_sha256 = "d29b635dd41aea62bd05229c7c7942d4b0aa38aee457f8dc7302b6e59acb721b"
_mw_db_name = "mediawiki"
_mw_db_user = "mediawiki"
_mw_db_password = "very-secret-password"
_mw_api_user = "wiki-scripts"
_mw_api_password = "super-secret-password"


def get_sha256sum(filename, blocksize=4096):
    m = hashlib.sha256()
    with open(filename, "rb") as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()

@pytest.fixture(scope="session")
def mw_server_root(request):
    cache_dir = request.config.cache.makedir("wiki-scripts mediawiki")
    tarball = os.path.join(cache_dir, "mediawiki-" + _mw_rel + ".tar.gz")
    server_root = os.path.join(cache_dir, "mediawiki-" + _mw_rel)

    if not os.path.isdir(server_root):
        # check if the tarball was downloaded correctly
        if os.path.isfile(tarball):
            _sha256 = get_sha256sum(tarball)
            if _sha256 != _mw_sha256:
                os.remove(tarball)

        # (re-)download MediaWiki sources only if the extracted dir does not exist
        if not os.path.isfile(tarball):
            r = requests.get(_mw_url, stream=True)
            with open(tarball, "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    f.write(chunk)
        # extract the tarball
        t = tarfile.open(tarball, "r")
        t.extractall(path=cache_dir)
        # server_root should be created by extraction
        assert os.path.isdir(server_root)

    return server_root

_php_ini = os.path.join(os.path.dirname(__file__), "../../misc/php.ini")
mw_nginx_proc = factories.nginx_php_proc("mw_server_root",
                                         php_fpm_params="--php-ini {}".format(_php_ini))

# direct connection to MediaWiki's database
mwpg_conn = postgresql("postgresql_proc", dbname=_mw_db_name)

class MediaWikiFixtureInstance:
    def __init__(self, mw_nginx_proc, postgresql_proc):
        self._mw_nginx_proc = mw_nginx_proc
        self._postgresql_proc = postgresql_proc

        # trivial aliases, usable also in tests
        self.hostname=mw_nginx_proc.host
        self.port=mw_nginx_proc.port

        # always write the config to reflect its possible updates
        self._init_local_settings()

        # init the database and users
        self._init_mw_database()

    def _init_local_settings(self):
        local_settings_php = os.path.join(os.path.dirname(__file__), "../../misc/LocalSettings.php")
        assert os.path.isfile(local_settings_php)
        config = open(local_settings_php).read()

        def replace_php_variable(config, name, value):
            c = re.sub(r"^(\${} *= *\").*(\";)$".format(name),
                       r"\g<1>{}\g<2>".format(value),
                       config,
                       flags=re.MULTILINE)
            _expected = "${} = \"{}\";".format(name, value)
            assert _expected in c, "String '{}' was not found after replacement.".format(_expected)
            return c

        config = replace_php_variable(config, "wgDBname", _mw_db_name)
        config = replace_php_variable(config, "wgDBuser", _mw_db_user)
        config = replace_php_variable(config, "wgDBpassword", _mw_db_password)
        config = replace_php_variable(config, "wgDBhost", self._postgresql_proc.host)
        config = replace_php_variable(config, "wgDBport", self._postgresql_proc.port)
        config = replace_php_variable(config, "wgServer", "http://{}:{}".format(self._mw_nginx_proc.host, self._mw_nginx_proc.port))

        output_settings = open(os.path.join(self._mw_nginx_proc.server_root, "LocalSettings.php"), "w")
        output_settings.write(config)
        output_settings.close()

    def _init_mw_database(self):
        # create database and mediawiki user
        master_url = sa.engine.url.URL("postgresql+psycopg",
                                       username=self._postgresql_proc.user,
                                       host=self._postgresql_proc.host,
                                       port=self._postgresql_proc.port)
        self._master_db_engine = sa.create_engine(master_url, isolation_level="AUTOCOMMIT")
        conn = self._master_db_engine.connect()
        r = conn.execute("SELECT count(*) FROM pg_user WHERE usename = '{}'".format(_mw_db_user))
        if r.fetchone()[0] == 0:
            conn.execute("CREATE USER {} WITH PASSWORD '{}'".format(_mw_db_user, _mw_db_password))
        conn.execute("CREATE DATABASE {} WITH OWNER {}".format(_mw_db_name, _mw_db_user))
        conn.close()

        # execute MediaWiki's tables.sql
        mw_url = sa.engine.url.URL("postgresql+psycopg",
                                   database=_mw_db_name,
                                   username=_mw_db_user,
                                   password=_mw_db_password,
                                   host=self._postgresql_proc.host,
                                   port=self._postgresql_proc.port)
        # use NullPool, so that we don't have to recreate the engine when we drop the database
        self.db_engine = sa.create_engine(mw_url, poolclass=sa.pool.NullPool)
        tables = open(os.path.join(self._mw_nginx_proc.server_root, "maintenance/postgres/tables.sql"))
        with self.db_engine.begin() as conn:
            conn.execute(tables.read())

        # create a wiki-scripts user in MediaWiki
        cmd = [
            "php",
            "--php-ini",
            _php_ini,
            "maintenance/createAndPromote.php",
            "--sysop",
            _mw_api_user,
            _mw_api_password,
        ]
        subprocess.run(cmd, cwd=self._mw_nginx_proc.server_root, check=True)

        # construct the API object for the new user wiki-scripts in the database
        api_url = "http://{host}:{port}/api.php".format(host=self.hostname, port=self.port)
        index_url = "http://{host}:{port}/index.php".format(host=self.hostname, port=self.port)
        self.api = API(api_url, index_url, API.make_session())
        self.api.login(_mw_api_user, _mw_api_password)

        # save the database as a template for self.clear()
        with self._master_db_engine.begin() as conn:
            conn.execute("SELECT pg_terminate_backend(pg_stat_activity.pid) "
                         "FROM pg_stat_activity WHERE pg_stat_activity.datname = '{}'"
                         .format(_mw_db_name))
            conn.execute("CREATE DATABASE {} WITH TEMPLATE {} OWNER {}"
                         .format(_mw_db_name + "_template", _mw_db_name, _mw_db_user))

    def _drop_mw_database(self):
        with self._master_db_engine.begin() as conn:
            # We cannot drop the database while there are connections to it, so we
            # first disallow new connections and terminate all connections to it.
            conn.execute("UPDATE pg_database SET datallowconn=false WHERE datname = '{}'".format(_mw_db_name))
            conn.execute("SELECT pg_terminate_backend(pg_stat_activity.pid) "
                         "FROM pg_stat_activity WHERE pg_stat_activity.datname = '{}'"
                         .format(_mw_db_name))
            conn.execute("DROP DATABASE IF EXISTS {}".format(_mw_db_name))

    def clear(self):
        """
        Tests which need the wiki to be in a predictable state should call this
        method to drop all content and then build up what they need.
        """
        # DROP DATABASE is much faster than TRUNCATE on all tables in the database.
        # CREATE DATABASE ... WITH TEMPLATE ... is faster than full re-initialization
        # and as a bonus does not mess up the session cache.
        self._drop_mw_database()
        with self._master_db_engine.begin() as conn:
            conn.execute("CREATE DATABASE {} WITH TEMPLATE {} OWNER {}"
                         .format(_mw_db_name, _mw_db_name + "_template", _mw_db_user))

    def run_jobs(self):
        cmd = [
            "php",
            "--php-ini",
            _php_ini,
            "maintenance/runJobs.php",
            "--result",
            "json",
        ]
        result = subprocess.run(cmd, cwd=self._mw_nginx_proc.server_root, check=True, capture_output=True)
#        pprint(json.loads(result.stdout))
        del self.api.site
        assert self.api.site.statistics["jobs"] == 0, "failed to execute all queued jobs"

@pytest.fixture(scope="session")
def mediawiki(mw_nginx_proc, postgresql_proc):
    instance = MediaWikiFixtureInstance(mw_nginx_proc, postgresql_proc)
    yield instance
    instance._drop_mw_database()

__all__ = ("mw_server_root", "mw_nginx_proc", "mediawiki")
