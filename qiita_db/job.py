"""
Objects for dealing with Qiita jobs

This module provides the implementation of the Job class.

Classes
-------
- `Job` -- A Qiita Job class
"""
# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import division
from json import dumps
from os import remove
from os.path import basename, join
from shutil import copy
from time import strftime
import date
from tarfile import open as taropen

from qiita_core.exceptions import IncompetentQiitaDeveloperError
from .base import QiitaStatusObject
from .util import insert_filepaths
from .make_environment import DFLT_BASE_WORK_FOLDER
from .exceptions import QiitaDBDuplicateError
from .sql_connection import SQLConnectionHandler


class Job(QiitaStatusObject):
    """
    Job object to access to the Qiita Job information

    Attributes
    ----------
    datatype
    command
    options
    results
    error_msg

    Methods
    -------
    set_error
    add_results
    """

    _table = "job"

    @staticmethod
    def _convert_to_id(value, table, conn_handler=None):
        """Converts a string value to it's corresponding table identifier

        Parameters
        ----------
        value : str
            The string value to convert
        table : str
            The table that has the conversion
        conn_handler : SQLConnectionHandler, optional
            The sql connection object

        Returns
        -------
        int
            The id correspinding to the string

        Raises
        ------
        IncompetentQiitaDeveloperError
            The passed string has no associated id
        """
        conn_handler = conn_handler if conn_handler else SQLConnectionHandler()
        _id = conn_handler.execute_fetchone(
            "SELECT {0}_id from {0} WHERE {0} = %s".format(table),
            (value, ))
        if _id is None:
            raise IncompetentQiitaDeveloperError("%s not valid for table %s"
                                                 % (value, table))

    @classmethod
    def exists(cls, datatype, command, options):
        """Checks if the given job already exists

        Parameters
        ----------
        datatype : str
            Datatype the job is operating on
        command : str
            The Qiime or other command run on the data
        options : str
            A sorted JSON string of the command options and their settings

        Returns
        -------
        bool
            Whether the job exists or not
        """
        sql = ("SELECT EXISTS(SELECT * FROM  qiita.{0} WHERE datatype = %s AND"
               " command = %s and options = %s)".format(cls._table))
        conn_handler = SQLConnectionHandler()
        datatype_id = cls._convert_to_id(datatype, "data_type", conn_handler)
        command_id = cls._convert_to_id(command, "data_type", conn_handler)
        return conn_handler(sql, (datatype_id, command_id, options))[0]

    @classmethod
    def create(cls, datatype, command, options, analysis):
        """Creates a new job on the database

        Parameters
        ----------
        datatype : str
            The datatype in which this job applies
        command : str
            The identifier of the command executed in this job
        options: dict
            The options for the command in format {option: value}
        analysis : str
            The analysis which this job belongs to

        Returns
        -------
        Job object
            The newly created job
        """
        if cls.exists(datatype, command, options):
            raise QiitaDBDuplicateError("Job already exists!")

        # Get the datatype and command ids from the strings
        conn_handler = SQLConnectionHandler()
        datatype_id = cls._convert_to_id(datatype, "data_type", conn_handler)
        command_id = cls._convert_to_id(command, "data_type", conn_handler)

        # JSON the options dictionary
        opts_json = dumps(options, sort_keys=True, separators=(',', ':'))
        # Create the job and return it
        sql = ("INSERT INTO qiita.{0} (data_type_id, job_status_id, "
               "command_id, options) VALUES "
               "(%s, %s, %s, %s) RETURN job_id").format(cls._table)
        job_id = conn_handler.execute_fetchone(sql, (datatype_id, command_id,
                                               opts_json, 1))[0]
        return cls(job_id)

    @property
    def datatype(self):
        """Returns the datatype of the job"""
        sql = ("SELECT data_type from qiita.data_type WHERE data_type_id = "
               "(SELECT data_type_id from qiita.{0} WHERE "
               "job_id = %s".format(self._table))
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(sql, (self._id, ))[0]

    @property
    def command(self):
        """Returns the command of the job"""
        sql = ("SELECT command from qiita.command WHERE data_type_id = "
               "(SELECT data_type_id from qiita.{0} WHERE "
               "job_id = %s".format(self._table))
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(sql, (self._id, ))[0]

    @property
    def options(self):
        """List of options used in the job"""
        sql = ("SELECT options FROM qiita.{0} WHERE "
               "job_id = %s".format(self._table))
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(sql, (self._id, ))[0]

    @property
    def results(self):
        """List of job result filepaths"""
        # tar = 7
        # Copy files to working dir, untar if necessary, then return filepaths
        sql = ("SELECT filepath, filepath_type_id FROM qiita.filepath WHERE "
               "filepath_id IN (SELECT filepath_id FROM "
               "qiita.job_results_filepath WHERE job_id = %s)")
        conn_handler = SQLConnectionHandler()
        results = conn_handler.execute_fetchall(sql, (self._id, ))
        results_untar = []
        for fp, fp_type in results:
            outpath = join(DFLT_BASE_WORK_FOLDER, basename(fp))
            if fp_type == 7:
                #untar to work directory
                with taropen(fp) as tar:
                    tar.extractall(path=outpath)
            else:
                #copy to work directory
                copy(fp, outpath)
            results_untar.append(outpath)
        return results_untar

    @property
    def error_msg(self):
        """String with an error message, if the job failed"""
        sql = ("SELECT msg FROM qiita.logging WHERE log_id = (SELECT log_id "
               "FROM qiita.{0} WHERE job_id = %s)".format(self._table))
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(sql, (self._id, ))[0]

# --- Functions ---
    def set_error(self, msg, severity):
        """Logs an error for the job

        Parameters
        ----------
        msg : str
            Error message/stacktrace if available
        severity: int
            Severity code of error
        """
        # insert the error into the logging table
        errtime = ' '.join((date.Today().isoformat(), strftime("%H:%M:%S")))
        sql = ("INSERT INTO qiita.logger VALUES (time, severity, msg) VALUES"
               "(%s, %s, %s) RETURNING log_id")
        conn_handler = SQLConnectionHandler()
        logid = conn_handler.execute_fetchone(sql, (errtime, severity, msg))

        # attach the error to the job
        sql = ("UPDATE qiita.{0} SET log_id = %s WHERE "
               "job_id = %s".format(self._table))
        conn_handler.execute(sql, (logid, self._id))

    def add_results(self, results):
        """Adds a list of results to the results

        Parameters
        ----------
            results : list of tuples
                filepath information to add to job, in format
                [(filepath, type_id), ...]
                Where type_id is the filepath type id of the filepath passed

        Notes
        -----
        If your results are a folder of files, pass the base folder as the
        filepath and the type_id as 7 (tar). This function will automatically
        tar the folder before adding it.

        Reference
        ---------
        [1] http://stackoverflow.com/questions/2032403/
            how-to-create-full-compressed-tar-file-using-python
        """
        # go though the list and tar any folders if necessary
        cleanup = []
        addpaths = []
        for fp, fp_type in results:
            outpath = join(DFLT_BASE_WORK_FOLDER, basename(fp))
            if fp_type == 7:
                with taropen(outpath, "w") as tar:
                    tar.add(fp, arcname=basename(fp))
                addpaths.append((outpath, 7))
                cleanup.append(outpath)
            else:
                addpaths.append((fp, fp_type))

        # add filepaths to the job
        conn_handler = SQLConnectionHandler()
        file_ids = insert_filepaths(addpaths, self._id, "job",
                                    "filepath", conn_handler)

        # associate filepaths with job
        sql = ("INSERT INTO qiita.{0}_results_fileapth (job_id, filepath_id"
               "VALUES (%s, %s)".format(self._table))
        conn_handler.execute_many(sql, [(self._id, fid) for fid in file_ids])

        # clean up the created tars from the working directory
        for path in cleanup:
            remove(path)
