r"""
Data objects (:mod: `qiita_db.data`)
====================================

..currentmodule:: qiita_db.data

This module provides functionality for inserting, querying and deleting
data stored in the database. There are three data classes available: `RawData`,
`PreprocessedData` and `ProcessedData`.

Classes
-------

..autosummary::
    :toctree: generated/

    BaseData
    RawData
    PreprocessedData
    ProcessedData

Examples
--------
Assume we have a raw data instance composed by two fastq files (the sequence
file 'seqs.fastq' and the barcodes file 'barcodes.fastq') that belongs to
study 1.

Inserting the raw data into the database:

>>> from qiita_db.data import RawData
>>> from qiita_db.study import Study
>>> study = Study(1) # doctest: +SKIP
>>> filepaths = [('seqs.fastq', 1), ('barcodes.fastq', 2)]
>>> rd = RawData.create(2, filepaths, study) # doctest: +SKIP
>>> print rd.id # doctest: +SKIP
2

Retrieve the filepaths associated with the raw data

>>> rd.get_filepaths() # doctest: +SKIP
[('seqs.fastq', 'raw_sequences'), ('barcodes.fastq', 'raw_barcodes')]

Assume we have preprocessed the previous raw data files using the parameters
under the first row in the 'preprocessed_sequence_illumina_params', and we
obtained to files: a fasta file 'seqs.fna' and a qual file 'seqs.qual'.

Inserting the preprocessed data into the database

>>> from qiita_db.data import PreprocessedData
>>> filepaths = [('seqs.fna', 4), ('seqs.qual', 5)]
>>> ppd = PreprocessedData.create(rd, "preprocessed_sequence_illumina_params",
...                               1, filepaths) # doctest: +SKIP
>>> print ppd.id # doctest: +SKIP
2

Assume we have processed the previous preprocessed data on June 2nd 2014 at 5pm
using uclust and the first set of parameters, and we obtained a BIOM table.

Inserting the processed data into the database:

>>> from qiita_db.data import ProcessedData
>>> from datetime import datetime
>>> filepaths = [('foo/table.biom', 6)]
>>> date = datetime(2014, 6, 2, 5, 0, 0)
>>> pd = ProcessedData(ppd, "processed_params_uclust", 1,
...                    filepaths, date) # doctest: +SKIP
>>> print pd.id # doctest: +SKIP
2
"""

# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from __future__ import division
from datetime import datetime
from os.path import join
from functools import partial


from qiita_core.exceptions import IncompetentQiitaDeveloperError
from .base import QiitaObject
from .sql_connection import SQLConnectionHandler
from .util import (exists_dynamic_table, get_db_files_base_dir,
                   insert_filepaths, convert_to_id, convert_from_id)
from .exceptions import QiitaDBColumnError
from .ontology import Ontology


class BaseData(QiitaObject):
    r"""Base class for the raw, preprocessed and processed data objects.

    Methods
    -------
    get_filepaths

    See Also
    --------
    RawData
    PreprocessedData
    PreprocessedData
    """
    _filepath_table = "filepath"

    # These variables should be defined in the subclasses. They are useful in
    # order to avoid code replication and be able to generalize the functions
    # included in this BaseClass
    _data_filepath_table = None
    _data_filepath_column = None

    def _link_data_filepaths(self, fp_ids, conn_handler):
        r"""Links the data `data_id` with its filepaths `fp_ids` in the DB
        connected with `conn_handler`

        Parameters
        ----------
        fp_ids : list of ints
            The filepaths ids to connect the data
        conn_handler : SQLConnectionHandler
            The connection handler object connected to the DB

        Raises
        ------
        IncompetentQiitaDeveloperError
            If called directly from the BaseClass or one of the subclasses does
            not define the class attributes _data_filepath_table and
            _data_filepath_column
        """
        # Create the list of SQL values to add
        values = [(self.id, fp_id) for fp_id in fp_ids]
        # Add all rows at once
        conn_handler.executemany(
            "INSERT INTO qiita.{0} ({1}, filepath_id) "
            "VALUES (%s, %s)".format(self._data_filepath_table,
                                     self._data_filepath_column), values)

    def _add_filepaths(self, filepaths, conn_handler):
        r"""Populates the DB tables for storing the filepaths and connects the
        `self` objects with these filepaths"""
        self._check_subclass()
        # Add the filepaths to the database
        fp_ids = insert_filepaths(filepaths, self._id, self._table,
                                  self._filepath_table, conn_handler)
        # Connect the raw data with its filepaths
        self._link_data_filepaths(fp_ids, conn_handler)

    def get_filepaths(self):
        r"""Returns the filepath associated with the data object

        Returns
        -------
        list of tuples
            A list of (path, filetype id) with all the paths associated with
            the current data
        """
        self._check_subclass()
        # We need a connection handler to the database
        conn_handler = SQLConnectionHandler()
        # Retrieve all the (path, id) tuples related with the current data
        # object. We need to first check the _data_filepath_table to get the
        # filepath ids of the filepath associated with the current data object.
        # We then can query the filepath table to get those paths/
        db_paths = conn_handler.execute_fetchall(
            "SELECT filepath, filepath_type_id FROM qiita.{0} WHERE "
            "filepath_id IN (SELECT filepath_id FROM qiita.{1} WHERE "
            "{2}=%(id)s)".format(self._filepath_table,
                                 self._data_filepath_table,
                                 self._data_filepath_column), {'id': self.id})
        return [(join(get_db_files_base_dir(conn_handler), fp),
                 convert_from_id(id, "filepath_type", conn_handler))
                for fp, id in db_paths]

    def get_filepath_ids(self):
        conn_handler = SQLConnectionHandler()
        db_ids = conn_handler.execute_fetchall(
            "SELECT filepath_id FROM qiita.{0} WHERE "
            "{1}=%(id)s".format(self._data_filepath_table,
                                self._data_filepath_column), {'id': self.id})
        return [fp_id[0] for fp_id in db_ids]


class RawData(BaseData):
    r"""Object for dealing with raw data

    Attributes
    ----------
    studies
    investigation_type

    Methods
    -------
    create
    data_type
    preprocessed_data

    See Also
    --------
    BaseData
    """
    # Override the class variables defined in the base classes
    _table = "raw_data"
    _data_filepath_table = "raw_filepath"
    _data_filepath_column = "raw_data_id"
    # Define here the class name, so in case it changes in the database we
    # only need to change it here
    _study_raw_table = "study_raw_data"

    @classmethod
    def create(cls, filetype, filepaths, studies, data_type_id,
               investigation_type=None):
        r"""Creates a new object with a new id on the storage system

        Parameters
        ----------
        filetype : int
            The filetype identifier
        filepaths : iterable of tuples (str, int)
            The list of paths to the raw files and its filepath type identifier
        studies : list of Study
            The list of Study objects to which the raw data belongs to
        data_type : int
            The data_type identifier
        investigation_type : str, optional
            The investigation type, if relevant

        Returns
        -------
        A new instance of `cls` to access to the RawData stored in the DB
        """
        # If the investigation_type is supplied, make sure if it is one of
        # the recognized investigation types
        if investigation_type is not None:
            investigation_types = Ontology(convert_to_id('ENA', 'ontology'))
            terms = investigation_types.terms
            if investigation_type not in terms:
                raise QiitaDBColumnError("Not a valid investigation_type. "
                                         "Choose from: %r" % terms)

        # Add the raw data to the database, and get the raw data id back
        conn_handler = SQLConnectionHandler()
        rd_id = conn_handler.execute_fetchone(
            "INSERT INTO qiita.{0} (filetype_id, investigation_type, "
            "data_type_id) VALUES (%s, %s, %s) "
            "RETURNING raw_data_id".format(cls._table),
            (filetype, investigation_type, data_type_id))[0]

        rd = cls(rd_id)

        # Connect the raw data with its studies
        values = [(study.id, rd_id) for study in studies]
        conn_handler.executemany(
            "INSERT INTO qiita.{0} (study_id, raw_data_id) VALUES "
            "(%s, %s)".format(rd._study_raw_table), values)

        rd._add_filepaths(filepaths, conn_handler)

        return rd

    @property
    def studies(self):
        r"""The IDs of the studies to which this raw data belongs

        Returns
        -------
        list of int
            The list of study ids to which the raw data belongs to
        """
        conn_handler = SQLConnectionHandler()
        ids = conn_handler.execute_fetchall(
            "SELECT study_id FROM qiita.{0} WHERE "
            "raw_data_id=%s".format(self._study_raw_table),
            [self._id])
        return [id[0] for id in ids]

    @property
    def filetype(self):
        r"""Returns the raw data filetype

        Returns
        -------
        str
            The raw data's filetype
        """
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT f.type FROM qiita.filetype f JOIN qiita.{0} r ON "
            "f.filetype_id = r.filetype_id WHERE "
            "r.raw_data_id=%s".format(self._table),
            (self._id,))[0]

    def data_type(self, ret_id=False):
        """Returns the data_type or data_type_id

        Parameters
        ----------
        ret_id : bool, optional
            Return the id instead of the string, default False

        Returns
        -------
        str or int
            string value of data_type or int if data_type_id
        """
        ret = "_id" if ret_id else ""
        conn_handler = SQLConnectionHandler()
        data_type = conn_handler.execute_fetchone(
            "SELECT d.data_type{0} FROM qiita.data_type d JOIN "
            "qiita.{1} c ON c.data_type_id = d.data_type_id WHERE"
            " c.raw_data_id = %s".format(ret, self._table), (self._id, ))
        return data_type[0]

    @property
    def investigation_type(self):
        conn_handler = SQLConnectionHandler()
        sql = ("SELECT investigation_type FROM qiita.{} "
               "where raw_data_id = %s".format(self._table))
        return conn_handler.execute_fetchone(sql, [self._id])[0]

    @property
    def preprocessing_status(self):
        r"""Tells if the data has been preprocessed or not

        Returns
        -------
        str
            One of {'not_preprocessed', 'preprocessing', 'success', 'failed'}
        """
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT preprocessing_status FROM qiita.{0} "
            "WHERE raw_data_id=%s".format(self._table), (self.id,))[0]

    @preprocessing_status.setter
    def preprocessing_status(self, state):
        r"""Update the preprocessing status

        Parameters
        ----------
        state : str, {'not_preprocessed', 'preprocessing', 'success', 'failed'}
            The current status of preprocessing

        Raises
        ------
        ValueError
            If the state is not known.
        """
        if (state not in ('not_preprocessed', 'preprocessing', 'success') and
                not state.startswith('failed:')):
            raise ValueError('Unknown state: %s' % state)

        conn_handler = SQLConnectionHandler()

        conn_handler.execute(
            "UPDATE qiita.{0} SET preprocessing_status = %s "
            "WHERE raw_data_id = %s".format(self._table),
            (state, self.id))

    @property
    def preprocessed_data(self):
        conn_handler = SQLConnectionHandler()
        sql = ("SELECT preprocessed_data_id FROM qiita.raw_preprocessed_data "
               "where raw_data_id = %s")
        return [x[0] for x in conn_handler.execute_fetchall(sql, (self._id,))]


class PreprocessedData(BaseData):
    r"""Object for dealing with preprocessed data

    Attributes
    ----------
    raw_data
    study

    Methods
    -------
    create
    is_submitted_to_insdc
    data_type

    See Also
    --------
    BaseData
    """
    # Override the class variables defined in the base classes
    _table = "preprocessed_data"
    _data_filepath_table = "preprocessed_filepath"
    _data_filepath_column = "preprocessed_data_id"
    _study_preprocessed_table = "study_preprocessed_data"
    _raw_preprocessed_table = "raw_preprocessed_data"

    @classmethod
    def create(cls, study, preprocessed_params_table, preprocessed_params_id,
               filepaths, raw_data=None, data_type=None,
               submitted_to_insdc_status='not submitted',
               ebi_submission_accession=None,
               ebi_study_accession=None):
        r"""Creates a new object with a new id on the storage system

        Parameters
        ----------
        study : Study
            The study to which this preprocessed data belongs to
        preprocessed_params_table : str
            Name of the table that holds the preprocessing parameters used
        preprocessed_params_id : int
            Identifier of the parameters from the `preprocessed_params_table`
            table used
        filepaths : iterable of tuples (str, int)
            The list of paths to the preprocessed files and its filepath type
            identifier
        submitted_to_insdc_status : str, {'not submitted', 'submitting', \
                'success', 'failed'} optional
            Submission status of the raw data files
        raw_data : RawData, optional
            The RawData object used as base to this preprocessed data
        data_type : str, optional
            The data_type of the preprocessed_data
        ebi_submission_accession : str, optional
            The ebi_submission_accession of the preprocessed_data
        ebi_study_accession : str, optional
            The ebi_study_accession of the preprocessed_data

        Raises
        ------
        IncompetentQiitaDeveloperError
            If the table `preprocessed_params_table` does not exists
        IncompetentQiitaDeveloperError
            If data_type does not match that of raw_data passed
        """
        conn_handler = SQLConnectionHandler()
        if (data_type and raw_data) and data_type != raw_data.data_type:
            raise IncompetentQiitaDeveloperError(
                "data_type passed does not match raw_data data_type!")
        elif data_type is None and raw_data is None:
            raise IncompetentQiitaDeveloperError("Neither data_type nor "
                                                 "raw_data passed!")
        elif raw_data:
            # raw_data passed but no data_type, so set to raw data data_type
            data_type = raw_data.data_type(ret_id=True)
        else:
            # only data_type, so need id from the text
            data_type = convert_to_id(data_type, "data_type", conn_handler)
        # Check that the preprocessed_params_table exists
        if not exists_dynamic_table(preprocessed_params_table, "preprocessed_",
                                    "_params", conn_handler):
            raise IncompetentQiitaDeveloperError(
                "Preprocessed params table '%s' does not exists!"
                % preprocessed_params_table)
        # Add the preprocessed data to the database,
        # and get the preprocessed data id back
        ppd_id = conn_handler.execute_fetchone(
            "INSERT INTO qiita.{0} (preprocessed_params_table, "
            "preprocessed_params_id, submitted_to_insdc_status, data_type_id, "
            "ebi_submission_accession, ebi_study_accession) VALUES "
            "(%(param_table)s, %(param_id)s, %(insdc)s, %(data_type)s, "
            "%(ebi_submission_accession)s, %(ebi_study_accession)s) "
            "RETURNING preprocessed_data_id".format(cls._table),
            {'param_table': preprocessed_params_table,
             'param_id': preprocessed_params_id,
             'insdc': submitted_to_insdc_status,
             'data_type': data_type,
             'ebi_submission_accession': ebi_submission_accession,
             'ebi_study_accession': ebi_study_accession})[0]
        ppd = cls(ppd_id)

        # Connect the preprocessed data with its study
        conn_handler.execute(
            "INSERT INTO qiita.{0} (study_id, preprocessed_data_id) "
            "VALUES (%s, %s)".format(ppd._study_preprocessed_table),
            (study.id, ppd.id))

        if raw_data is not None:
            # Connect the preprocessed data with the raw data
            conn_handler.execute(
                "INSERT INTO qiita.{0} (raw_data_id, preprocessed_data_id) "
                "VALUES (%s, %s)".format(cls._raw_preprocessed_table),
                (raw_data.id, ppd_id))

        ppd._add_filepaths(filepaths, conn_handler)
        return ppd

    @property
    def raw_data(self):
        r"""The raw data id used to generate the preprocessed data"""
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT raw_data_id FROM qiita.{0} WHERE "
            "preprocessed_data_id=%s".format(self._raw_preprocessed_table),
            [self._id])[0]

    @property
    def study(self):
        r"""The ID of the study to which this preprocessed data belongs

        Returns
        -------
        int
            The study id to which this preprocessed data belongs to"""
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT study_id FROM qiita.{0} WHERE "
            "preprocessed_data_id=%s".format(self._study_preprocessed_table),
            [self._id])[0]

    @property
    def ebi_submission_accession(self):
        r"""The ebi submission accession of this preprocessed data

        Returns
        -------
        str
            The ebi submission accession of this preprocessed data
        """
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT ebi_submission_accession FROM qiita.{0} "
            "WHERE preprocessed_data_id=%s".format(self._table), (self.id,))[0]

    @property
    def ebi_study_accession(self):
        r"""The ebi study accession of this preprocessed data

        Returns
        -------
        str
            The ebi study accession of this preprocessed data
        """
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT ebi_study_accession FROM qiita.{0} "
            "WHERE preprocessed_data_id=%s".format(self._table), (self.id,))[0]

    @ebi_submission_accession.setter
    def ebi_submission_accession(self, new_ebi_submission_accession):
        """ Sets the ebi_submission_accession for the preprocessed_data

        Parameters
        ----------
        new_ebi_submission_accession: str
            The new ebi submission accession
        """
        conn_handler = SQLConnectionHandler()

        sql = ("UPDATE qiita.{0} SET ebi_submission_accession = %s WHERE "
               "preprocessed_data_id = %s").format(self._table)
        conn_handler.execute(sql, (new_ebi_submission_accession, self._id))

    @ebi_study_accession.setter
    def ebi_study_accession(self, new_ebi_study_accession):
        """ Sets the ebi_study_accession for the preprocessed_data

        Parameters
        ----------
        new_ebi_study_accession: str
            The new ebi study accession
        """
        conn_handler = SQLConnectionHandler()

        sql = ("UPDATE qiita.{0} SET ebi_study_accession = %s WHERE "
               "preprocessed_data_id = %s").format(self._table)
        conn_handler.execute(sql, (new_ebi_study_accession, self._id))

    def data_type(self, ret_id=False):
        """Returns the data_type or data_type_id

        Parameters
        ----------
        ret_id : bool, optional
            Return the id instead of the string, default False

        Returns
        -------
        str or int
            string value of data_type or data_type_id
        """
        conn_handler = SQLConnectionHandler()
        ret = "_id" if ret_id else ""
        data_type = conn_handler.execute_fetchone(
            "SELECT d.data_type{0} FROM qiita.data_type d JOIN "
            "qiita.{1} p ON p.data_type_id = d.data_type_id WHERE"
            " p.preprocessed_data_id = %s".format(ret, self._table),
            (self._id, ))
        return data_type[0]

    def submitted_to_insdc_status(self):
        r"""Tells if the raw data has been submitted to INSDC

        Returns
        -------
        str
            One of {'not submitted', 'submitting', 'success', 'failed'}
        """
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT submitted_to_insdc_status FROM qiita.{0} "
            "WHERE preprocessed_data_id=%s".format(self._table), (self.id,))[0]

    def update_insdc_status(self, state, study_acc=None, submission_acc=None):
        r"""Update the INSDC submission status

        Parameters
        ----------
        state : str, {'not submitted', 'submitting', 'success', 'failed'}
            The current status of submission
        study_acc : str, optional
            The study accession from EBI. This is not optional if ``state`` is
            ``success``.
        submission_acc : str, optional
            The submission accession from EBI. This is not optional if
            ``state`` is ``success``.

        Raises
        ------
        ValueError
            If the state is not known.
        ValueError
            If ``state`` is ``success`` and either ``study_acc`` or
            ``submission_acc`` are ``None``.
        """
        if state not in ('not submitted', 'submitting', 'success', 'failed'):
            raise ValueError("Unknown state: %s" % state)

        conn_handler = SQLConnectionHandler()

        if state == 'success':
            if study_acc is None or submission_acc is None:
                raise ValueError("study_acc or submission_acc is None!")

            conn_handler.execute("""
                UPDATE qiita.{0}
                SET (submitted_to_insdc_status,
                     ebi_study_accession,
                     ebi_submission_accession) = (%s, %s, %s)
                WHERE preprocessed_data_id=%s""".format(self._table),
                                 (state, study_acc, submission_acc, self.id))
        else:
            conn_handler.execute("""
                UPDATE qiita.{0}
                SET submitted_to_insdc_status = %s
                WHERE preprocessed_data_id=%s""".format(self._table),
                                 (state, self.id))


class ProcessedData(BaseData):
    r"""Object for dealing with processed data

    Attributes
    ----------
    preprocessed_data
    study

    Methods
    -------
    create
    data_type

    See Also
    --------
    BaseData
    """
    # Override the class variables defined in the base classes
    _table = "processed_data"
    _data_filepath_table = "processed_filepath"
    _data_filepath_column = "processed_data_id"
    _study_processed_table = "study_processed_data"
    _preprocessed_processed_table = "preprocessed_processed_data"

    @classmethod
    def create(cls, processed_params_table, processed_params_id, filepaths,
               preprocessed_data=None, study=None, processed_date=None,
               data_type=None):
        r"""
        Parameters
        ----------
        processed_params_table : str
            Name of the table that holds the preprocessing parameters used
        processed_params_id : int
            Identifier of the parameters from the `processed_params_table`
            table used
        filepaths : iterable of tuples (str, int)
            The list of paths to the processed files and its filepath type
            identifier
        preprocessed_data : PreprocessedData, optional
            The PreprocessedData object used as base to this processed data
        study : Study, optional
            If preprocessed_data is not provided, the study the processed data
            belongs to
        processed_date : datetime, optional
            Date in which the data have been processed. Default: now
        data_type : str, optional
            data_type of the processed_data. Otherwise taken from passed
            preprocessed_data.

        Raises
        ------
        IncompetentQiitaDeveloperError
            If the table `processed_params_table` does not exists
            If `preprocessed_data` and `study` are provided at the same time
            If `preprocessed_data` and `study` are not provided
        """
        conn_handler = SQLConnectionHandler()
        if preprocessed_data is not None:
            if study is not None:
                raise IncompetentQiitaDeveloperError(
                    "You should provide either preprocessed_data or study, "
                    "but not both")
            elif data_type is not None and \
                    data_type != preprocessed_data.data_type():
                raise IncompetentQiitaDeveloperError(
                    "data_type passed does not match preprocessed_data "
                    "data_type!")
            else:
                data_type = preprocessed_data.data_type(ret_id=True)
        else:
            if study is None:
                raise IncompetentQiitaDeveloperError(
                    "You should provide either a preprocessed_data or a study")
            if data_type is None:
                raise IncompetentQiitaDeveloperError(
                    "You must provide either a preprocessed_data, a "
                    "data_type, or both")
            else:
                data_type = convert_to_id(data_type, "data_type", conn_handler)

        # We first check that the processed_params_table exists
        if not exists_dynamic_table(processed_params_table,
                                    "processed_params_", "", conn_handler):
            raise IncompetentQiitaDeveloperError(
                "Processed params table %s does not exists!"
                % processed_params_table)

        # Check if we have received a date:
        if processed_date is None:
            processed_date = datetime.now()

        # Add the processed data to the database,
        # and get the processed data id back
        pd_id = conn_handler.execute_fetchone(
            "INSERT INTO qiita.{0} (processed_params_table, "
            "processed_params_id, processed_date, data_type_id) VALUES ("
            "%(param_table)s, %(param_id)s, %(date)s, %(data_type)s) RETURNING"
            " processed_data_id".format(cls._table),
            {'param_table': processed_params_table,
             'param_id': processed_params_id,
             'date': processed_date,
             'data_type': data_type})[0]

        pd = cls(pd_id)

        if preprocessed_data is not None:
            conn_handler.execute(
                "INSERT INTO qiita.{0} (preprocessed_data_id, "
                "processed_data_id) VALUES "
                "(%s, %s)".format(cls._preprocessed_processed_table),
                (preprocessed_data.id, pd_id))
            study_id = preprocessed_data.study
        else:
            study_id = study.id

        # Connect the processed data with the study
        conn_handler.execute(
            "INSERT INTO qiita.{0} (study_id, processed_data_id) VALUES "
            "(%s, %s)".format(cls._study_processed_table),
            (study_id, pd_id))

        pd._add_filepaths(filepaths, conn_handler)
        return cls(pd_id)

    @property
    def preprocessed_data(self):
        r"""The preprocessed data id used to generate the processed data"""
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT preprocessed_data_id FROM qiita.{0} WHERE "
            "processed_data_id=%s".format(self._preprocessed_processed_table),
            [self._id])[0]

    @property
    def study(self):
        r"""The ID of the study to which this processed data belongs

        Returns
        -------
        int
            The study id to which this processed data belongs"""
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT study_id FROM qiita.{0} WHERE "
            "processed_data_id=%s".format(self._study_processed_table),
            [self._id])[0]

    def data_type(self, ret_id=False):
        """Returns the data_type or data_type_id

        Parameters
        ----------
        ret_id : bool, optional
            Return the id instead of the string, default False

        Returns
        -------
        str or int
            string value of data_type or data_type_id
        """
        conn_handler = SQLConnectionHandler()
        ret = "_id" if ret_id else ""
        data_type = conn_handler.execute_fetchone(
            "SELECT d.data_type{0} FROM qiita.data_type d JOIN "
            "qiita.{1} p ON p.data_type_id = d.data_type_id WHERE"
            " p.processed_data_id = %s".format(ret, self._table),
            (self._id, ))
        return data_type[0]
