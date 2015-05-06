# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import division
from os.path import join, dirname, basename, exists
from shutil import move
from glob import glob
import re

from .base import QiitaObject
from .exceptions import QiitaDBDuplicateError, QiitaDBError
from .util import (insert_filepaths, convert_to_id,
                   get_mountpoint)
from .sql_connection import SQLConnectionHandler


def _rename_sortmerna_indexed_db_files(smr_db, db_name, db_version):
    """Renames the SortMeRNA indexed db files to use a controlled name

    Parameters
    ----------
    smr_db : str
        The base path to the sortmerna_indexed_db
    db_name : str
        The name of the reference database
    db_version : str
        The version of the reference database

    Raises
    ------
    QiitaDBError
        If smr_db does not contain a correct SortMeRNA indexed db
    """
    smr_db_dir = dirname(smr_db)

    # Rename the .stats file
    old_fp = "%s.stats" % smr_db
    if not exists(old_fp):
        raise QiitaDBError(
            "%s does not look like a correct SortMeRNA indexed database."
            % smr_db)

    new_fp = join(smr_db_dir, "%s_%s.stats" % (db_name, db_version))

    fps_to_rename = [(old_fp, new_fp)]

    suff = ["pos", "bursttrie", "kmer"]

    for s in suff:
        g_re = "%s.%s_[0-9]*.dat" % (smr_db, s)
        s_re = "\.%s_(\d+)\.dat" % s

        old_fps = glob(g_re)

        if not old_fps:
            raise QiitaDBError(
                "%s does not look like a correct SortMeRNA indexed database."
                % smr_db)

        for old_fp in old_fps:
            result = re.search(s_re, basename(old_fp))

            if result:
                idx = int(result.group(1))
                new_fn = "%s_%s.%s_%d.dat" % (db_name, db_version, s, idx)
                new_fp = join(smr_db_dir, new_fn)
                fps_to_rename.append((old_fp, new_fp))

    for old_fp, new_fp in fps_to_rename:
        move(old_fp, new_fp)


class Reference(QiitaObject):
    r"""Object to interact with reference sequence databases

    Attributes
    ----------
    sequence_fp
    taxonomy_fp
    tree_fp
    sortmerna_indexed_db

    Methods
    -------
    create
    exists

    See Also
    --------
    QiitaObject
    """
    _table = "reference"

    @classmethod
    def create(cls, name, version, seqs_fp, tax_fp=None, tree_fp=None,
               sortmerna_indexed_db=None):
        r"""Creates a new reference object with a new id on the storage system

        Parameters
        ----------
        name : str
            The name of the reference database
        version : str
            The version of the reference database
        seqs_fp : str
            The path to the reference sequence file
        tax_fp : str, optional
            The path to the reference taxonomy file
        tree_fp : str, optional
            The path to the reference tree file
        sortmerna_indexed_db : str, optional
            The base path to the sortmerna_indexed_db

        Returns
        -------
        A new instance of `cls` to access to the Reference stored in the DB

        Raises
        ------
        QiitaDBDuplicateError
            If the reference database with name `name` and version `version`
            already exists on the system
        QiitaDBWarning
            If sortmerna_indexed_db is not passed
        """
        if cls.exists(name, version):
            raise QiitaDBDuplicateError("Reference",
                                        "Name: %s, Version: %s"
                                        % (name, version))

        conn_handler = SQLConnectionHandler()

        seq_id = insert_filepaths([(seqs_fp, convert_to_id("reference_seqs",
                                                           "filepath_type"))],
                                  "%s_%s" % (name, version), "reference",
                                  "filepath", conn_handler)[0]

        # Check if the database has taxonomy file
        tax_id = None
        if tax_fp:
            fps = [(tax_fp, convert_to_id("reference_tax", "filepath_type"))]
            tax_id = insert_filepaths(fps, "%s_%s" % (name, version),
                                      "reference", "filepath", conn_handler)[0]

        # Check if the database has tree file
        tree_id = None
        if tree_fp:
            fps = [(tree_fp, convert_to_id("reference_tree", "filepath_type"))]
            tree_id = insert_filepaths(fps, "%s_%s" % (name, version),
                                       "reference", "filepath",
                                       conn_handler)[0]

        # Check if the SortMeRNA indexed database have been provided
        smr_id = None
        if sortmerna_indexed_db:
            _rename_sortmerna_indexed_db_files(sortmerna_indexed_db, name,
                                               version)

            fps = [(dirname(sortmerna_indexed_db),
                    convert_to_id("directory", "filepath_type"))]
            smr_id = insert_filepaths(fps, "%s_%s_smr_idx" % (name, version),
                                      "reference", "filepath", conn_handler)[0]

        # Insert the actual object to the db
        ref_id = conn_handler.execute_fetchone(
            "INSERT INTO qiita.{0} (reference_name, reference_version, "
            "sequence_filepath, taxonomy_filepath, tree_filepath, "
            "sortmerna_indexed_db_filepath) VALUES (%s, %s, %s, %s, %s, %s) "
            "RETURNING reference_id".format(cls._table),
            (name, version, seq_id, tax_id, tree_id, smr_id))[0]

        return cls(ref_id)

    @classmethod
    def exists(cls, name, version):
        r"""Checks if a given object info is already present on the DB

        Parameters
        ----------
        name : str
            The name of the reference database
        version : str
            The version of the reference database

        Raises
        ------
        QiitaDBNotImplementedError
            If the method is not overwritten by a subclass
        """
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT EXISTS(SELECT * FROM qiita.{0} WHERE "
            "reference_name=%s AND reference_version=%s)".format(cls._table),
            (name, version))[0]

    @property
    def name(self):
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT reference_name FROM qiita.{0} WHERE "
            "reference_id = %s".format(self._table), (self._id,))[0]
        _, basefp = get_mountpoint('reference')[0]

    @property
    def version(self):
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT reference_version FROM qiita.{0} WHERE "
            "reference_id = %s".format(self._table), (self._id,))[0]
        _, basefp = get_mountpoint('reference')[0]

    @property
    def sequence_fp(self):
        conn_handler = SQLConnectionHandler()
        rel_path = conn_handler.execute_fetchone(
            "SELECT f.filepath FROM qiita.filepath f JOIN qiita.{0} r ON "
            "r.sequence_filepath=f.filepath_id WHERE "
            "r.reference_id=%s".format(self._table), (self._id,))[0]
        _, basefp = get_mountpoint('reference')[0]
        return join(basefp, rel_path)

    @property
    def taxonomy_fp(self):
        conn_handler = SQLConnectionHandler()
        rel_path = conn_handler.execute_fetchone(
            "SELECT f.filepath FROM qiita.filepath f JOIN qiita.{0} r ON "
            "r.taxonomy_filepath=f.filepath_id WHERE "
            "r.reference_id=%s".format(self._table), (self._id,))

        if not rel_path:
            return None

        _, basefp = get_mountpoint('reference')[0]
        return join(basefp, rel_path[0])

    @property
    def tree_fp(self):
        conn_handler = SQLConnectionHandler()
        rel_path = conn_handler.execute_fetchone(
            "SELECT f.filepath FROM qiita.filepath f JOIN qiita.{0} r ON "
            "r.tree_filepath=f.filepath_id WHERE "
            "r.reference_id=%s".format(self._table), (self._id,))

        if not rel_path:
            return None

        _, basefp = get_mountpoint('reference')[0]
        return join(basefp, rel_path[0])

    @property
    def sortmerna_db(self):
        conn_handler = SQLConnectionHandler()
        rel_path = conn_handler.execute_fetchone(
            "SELECT f.filepath "
            "FROM qiita.filepath f "
            "JOIN qiita.{0} r ON r.sortmerna_indexed_db_filepath=f.filepath_id"
            " WHERE r.reference_id=%s".format(self._table),
            (self._id,))

        if not rel_path:
            return None

        base_fp = get_mountpoint('reference')[0][1]
        return join(base_fp, rel_path[0], "%s_%s" % (self.name, self.version))
