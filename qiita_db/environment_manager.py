# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from os.path import abspath, dirname, join
from functools import partial
from os import remove, close
from tempfile import mkstemp
from ftplib import FTP
import gzip

from future import standard_library
with standard_library.hooks():
    from urllib.request import urlretrieve
from psycopg2 import connect
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from qiita_core.exceptions import QiitaEnvironmentError
from qiita_db.util import get_db_files_base_dir

get_support_file = partial(join, join(dirname(abspath(__file__)),
                                      'support_files'))

DFLT_BASE_WORK_FOLDER = get_support_file('work_data')
SETTINGS_FP = get_support_file('qiita-db-settings.sql')
LAYOUT_FP = get_support_file('qiita-db.sql')
INITIALIZE_FP = get_support_file('initialize.sql')
POPULATE_FP = get_support_file('populate_test_db.sql')
ENVIRONMENTS = {'demo': 'qiita_demo', 'test': 'qiita_test'}
CLUSTERS = ['demo', 'reserved', 'general']


def _check_db_exists(db, cursor):
    r"""Checks if the database db exists on the postgres server

    Parameters
    ----------
    db : str
        The database
    cursor : psycopg2.cursor
        The cursor connected to the database
    """
    cursor.execute('SELECT datname FROM pg_database')
    # It's a list of tuples, so just create the tuple to check if exists
    return (db,) in cursor.fetchall()


def make_environment(env, base_data_dir, base_work_dir, user, password, host,
                     load_ontologies):
    r"""Creates the new environment `env`

    Parameters
    ----------
    env : {demo, test}
        The environment to create

    Raises
    ------
    ValueError
        If `env` not recognized
    """
    if env not in ENVIRONMENTS:
        raise ValueError("Environment %s not recognized. Available "
                         "environments are %s" % (env, ENVIRONMENTS.keys()))
    # Connect to the postgres server
    conn = connect(user=user, host=host, password=password)
    # Set the isolation level to AUTOCOMMIT so we can execute a create database
    # sql quary
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    # Get the cursor
    cur = conn.cursor()
    # Check that it does not already exists
    if _check_db_exists(ENVIRONMENTS[env], cur):
        print("Environment {0} already present on the system. You can drop "
              "it by running `qiita_env drop_env --env {0}".format(env))
    else:
        # Create the database
        print('Creating database')
        cur.execute('CREATE DATABASE %s' % ENVIRONMENTS[env])
        cur.close()
        conn.close()

        # Connect to the postgres server, but this time to the just created db
        conn = connect(user=user, host=host, password=password,
                       database=ENVIRONMENTS[env])
        cur = conn.cursor()

        print('Inserting database metadata')
        # Build the SQL layout into the database
        with open(SETTINGS_FP, 'U') as f:
            cur.execute(f.read())

        # Insert the settings values to the database
        cur.execute("INSERT INTO settings (test, base_data_dir, base_work_dir)"
                    " VALUES (TRUE, '%s', '%s')"
                    % (base_data_dir, base_work_dir))

        if env == 'demo':
            # Create the schema
            print('Building SQL layout')
            with open(LAYOUT_FP, 'U') as f:
                cur.execute(f.read())

            print('Initializing database')
            # Initialize the database
            with open(INITIALIZE_FP, 'U') as f:
                cur.execute(f.read())
            if load_ontologies:
                print ('Loading Ontology Data')
                ontos_fp, f = download_and_unzip_file(
                    host='thebeast.colorado.edu',
                    filename='/pub/qiita/qiita_ontoandvocab.sql.gz')
                cur.execute(f.read())
                f.close()
                remove(ontos_fp)

            # Commit all the changes and close the connections
            print('Populating database with demo data')
            cur.execute(
                "INSERT INTO qiita.qiita_user (email, user_level_id, password,"
                " name, affiliation, address, phone) VALUES "
                "('demo@microbio.me', 4, "
                "'$2a$12$gnUi8Qg.0tvW243v889BhOBhWLIHyIJjjgaG6dxuRJkUM8nXG9Efe"
                "', 'Demo', 'Qitta Dev', '1345 Colorado Avenue', "
                "'303-492-1984');")

            conn.commit()
            cur.close()
            conn.close()

            print('Downloading test files')
            # Download tree file
            url = ("https://raw.githubusercontent.com/biocore/Evident/master"
                   "/data/gg_97_otus_4feb2011.tre")
            try:
                urlretrieve(url, join(base_data_dir, "reference",
                                      "gg_97_otus_4feb2011.tre"))
            except:
                raise IOError("Error: DOWNLOAD FAILED")

            print('Demo environment successfully created')
        elif env == "test":
            # Create the schema
            print('Create schema in test database')
            with open(LAYOUT_FP, 'U') as f:
                cur.execute(f.read())
            print('Populate the test database')
            # Initialize the database
            with open(INITIALIZE_FP, 'U') as f:
                cur.execute(f.read())
            # Populate the database
            with open(POPULATE_FP, 'U') as f:
                cur.execute(f.read())
            conn.commit()
            cur.close()
            conn.close()
            print('Test environment successfully created')
        else:
            # Commit all the changes and close the connections
            conn.commit()
            cur.close()
            conn.close()


def drop_environment(env, user, password, host):
    r"""Drops the `env` environment.

    Parameters
    ----------
    env : {demo, test}
        The environment to create
    user : str
        The postgres user to connect to the server
    password : str
        The password of the user
    host : str
        The host where the postgres server is running
    """
    # Connect to the postgres server
    conn = connect(user=user, host=host, password=password)
    # Set the isolation level to AUTOCOMMIT so we can execute a
    # drop database sql query
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    # Drop the database
    cur = conn.cursor()

    if not _check_db_exists(ENVIRONMENTS[env], cur):
        raise QiitaEnvironmentError(
            "Test environment not present on the system. You can create it "
            "by running 'qiita_env make_test_env'")

    if env == 'demo':
        # wipe the overwriiten test files so empty as on repo
        base = get_db_files_base_dir()
        with open(join(base, "reference",
                       "gg_97_otus_4feb2011.tre"), 'w') as f:
            f.write('\n')

    cur.execute('DROP DATABASE %s' % ENVIRONMENTS[env])
    # Close cursor and connection
    cur.close()
    conn.close()


def clean_test_environment(user, password, host):
    r"""Cleans the test database environment.

    In case that the test database is dirty (i.e. the 'qiita' schema is
    present), this cleans it up by dropping the 'qiita' schema and
    re-populating it.

    Parameters
    ----------
    user : str
        The postgres user to connect to the server
    password : str
        The password of the user
    host : str
        The host where the postgres server is running
    """
    # Connect to the postgres server
    conn = connect(user=user, host=host, password=password,
                   database='qiita_test')
    # Get the cursor
    cur = conn.cursor()
    # Drop the qiita schema
    cur.execute("DROP SCHEMA qiita CASCADE")
    # Commit the changes
    conn.commit()
    # Close cursor and connections
    cur.close()
    conn.close()


def download_and_unzip_file(host, filename):
    """Function downloads though ftp and unzips a file

    Parameters
    -----------
    host : str
        the location of the ftp server that is hosting the file
    filename : str
        the location of the file on the ftp server to download
    """
    handl, tmpfile = mkstemp()
    close(handl)
    ftp = FTP(host)
    ftp.login()
    cmd = 'RETR %s' % filename
    ftp.retrbinary(cmd, open(tmpfile, 'wb').write)
    f = gzip.open(tmpfile, 'rb')
    return tmpfile, f
