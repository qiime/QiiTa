r"""
Metadata template objects (:mod: `qiita_db.metadata_template)
=============================================================

..currentmodule:: qiita_db.metadata_template

This module provides the MetadataTemplate base class and the subclasses
SampleTemplate and PrepTemplate.

Classes
-------

..autosummary::
    :toctree: generated/

    BaseSample
    Sample
    PrepSample
    MetadataTemplate
    SampleTemplate
    PrepTemplate

Methods
-------

..autosummary::
    :toctree: generated/
"""

# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from __future__ import division
from future.utils import viewitems, viewvalues
from future.builtins import zip
from os.path import join
from functools import partial
from collections import defaultdict
from copy import deepcopy

import pandas as pd
from skbio.util import find_duplicates
import warnings

from qiita_core.exceptions import IncompetentQiitaDeveloperError

from qiita_db.exceptions import (QiitaDBUnknownIDError, QiitaDBColumnError,
                                 QiitaDBNotImplementedError, QiitaDBError,
                                 QiitaDBWarning, QiitaDBDuplicateHeaderError)
from qiita_db.base import QiitaObject
from qiita_db.sql_connection import SQLConnectionHandler
from qiita_db.util import (exists_table, get_table_cols,
                           get_mountpoint, insert_filepaths)
from qiita_db.logger import LogEntry
from .util import (as_python_types, get_datatypes, get_invalid_sample_names,
                   prefix_sample_names_with_id)


class BaseSample(QiitaObject):
    r"""Sample object that accesses the db to get the information of a sample
    belonging to a PrepTemplate or a SampleTemplate.

    Parameters
    ----------
    sample_id : str
        The sample id
    md_template : MetadataTemplate
        The metadata template obj to which the sample belongs to

    Methods
    -------
    __eq__
    __len__
    __getitem__
    __setitem__
    __delitem__
    __iter__
    __contains__
    exists
    keys
    values
    items
    get

    See Also
    --------
    QiitaObject
    Sample
    PrepSample
    """
    # Used to find the right SQL tables - should be defined on the subclasses
    _table_prefix = None
    _column_table = None
    _id_column = None

    def _check_template_class(self, md_template):
        r"""Checks that md_template is of the correct type

        Parameters
        ----------
        md_template : MetadataTemplate
            The metadata template

        Raises
        ------
        IncompetentQiitaDeveloperError
            If its call directly from the Base class
            If `md_template` doesn't have the correct type
        """
        raise IncompetentQiitaDeveloperError()

    def __init__(self, sample_id, md_template):
        r"""Initializes the object

        Parameters
        ----------
        sample_id : str
            The sample id
        md_template : MetadataTemplate
            The metadata template in which the sample is present

        Raises
        ------
        QiitaDBUnknownIDError
            If `sample_id` does not correspond to any sample in md_template
        """
        # Check that we are not instantiating the base class
        self._check_subclass()
        # Check that the md_template is of the correct type
        self._check_template_class(md_template)
        # Check if the sample id is present on the passed metadata template
        # This test will check that the sample id is actually present on the db
        if sample_id not in md_template:
            raise QiitaDBUnknownIDError(sample_id, self.__class__.__name__)
        # Assign private attributes
        self._id = sample_id
        self._md_template = md_template
        self._dynamic_table = "%s%d" % (self._table_prefix,
                                        self._md_template.id)

    def __hash__(self):
        r"""Defines the hash function so samples are hashable"""
        return hash(self._id)

    def __eq__(self, other):
        r"""Self and other are equal based on type and ids"""
        if not isinstance(other, type(self)):
            return False
        if other._id != self._id:
            return False
        if other._md_template != self._md_template:
            return False
        return True

    @classmethod
    def exists(cls, sample_id, md_template):
        r"""Checks if already exists a MetadataTemplate for the provided object

        Parameters
        ----------
        sample_id : str
            The sample id
        md_template : MetadataTemplate
            The metadata template to which the sample belongs to

        Returns
        -------
        bool
            True if already exists. False otherwise.
        """
        cls._check_subclass()
        conn_handler = SQLConnectionHandler()
        return conn_handler.execute_fetchone(
            "SELECT EXISTS(SELECT * FROM qiita.{0} WHERE sample_id=%s AND "
            "{1}=%s)".format(cls._table, cls._id_column),
            (sample_id, md_template.id))[0]

    def _get_categories(self, conn_handler):
        r"""Returns all the available metadata categories for the sample

        Parameters
        ----------
        conn_handler : SQLConnectionHandler
            The connection handler object connected to the DB

        Returns
        -------
        set of str
            The set of all available metadata categories
        """
        # Get all the columns
        cols = get_table_cols(self._dynamic_table)
        # Remove the sample_id column as this column is used internally for
        # data storage and it doesn't actually belong to the metadata
        cols.remove('sample_id')

        return set(cols)

    def _to_dict(self):
        r"""Returns the categories and their values in a dictionary

        Returns
        -------
        dict of {str: str}
            A dictionary of the form {category: value}
        """
        conn_handler = SQLConnectionHandler()
        d = dict(conn_handler.execute_fetchone(
            "SELECT * from qiita.{0} WHERE "
            "sample_id=%s".format(self._dynamic_table),
            (self._id, )))

        # Remove the sample_id, is not part of the metadata
        del d['sample_id']

        return d

    def __len__(self):
        r"""Returns the number of metadata categories

        Returns
        -------
        int
            The number of metadata categories
        """
        conn_handler = SQLConnectionHandler()
        # return the number of columns
        return len(self._get_categories(conn_handler))

    def __getitem__(self, key):
        r"""Returns the value of the metadata category `key`

        Parameters
        ----------
        key : str
            The metadata category

        Returns
        -------
        obj
            The value of the metadata category `key`

        Raises
        ------
        KeyError
            If the metadata category `key` does not exists

        See Also
        --------
        get
        """
        conn_handler = SQLConnectionHandler()
        key = key.lower()
        if key not in self._get_categories(conn_handler):
            # The key is not available for the sample, so raise a KeyError
            raise KeyError("Metadata category %s does not exists for sample %s"
                           " in template %d" %
                           (key, self._id, self._md_template.id))

        sql = """SELECT {0} FROM qiita.{1}
                 WHERE sample_id=%s""".format(key, self._dynamic_table)

        return conn_handler.execute_fetchone(sql, (self._id, ))[0]

    def add_setitem_queries(self, column, value, conn_handler, queue):
        """Adds the SQL queries needed to set a value to the provided queue

        Parameters
        ----------
        column : str
            The column to update
        value : str
            The value to set. This is expected to be a str on the assumption
            that psycopg2 will cast as necessary when updating.
        conn_handler : SQLConnectionHandler
            The connection handler object connected to the DB
        queue : str
            The queue where the SQL statements will be added

        Raises
        ------
        QiitaDBColumnError
            If the column does not exist in the table
        """
        # Check if the column exist in the table
        if column not in self._get_categories(conn_handler):
            raise QiitaDBColumnError("Column %s does not exist in %s" %
                                     (column, self._dynamic_table))

        sql = """UPDATE qiita.{0}
                 SET {1}=%s
                 WHERE sample_id=%s""".format(self._dynamic_table, column)

        conn_handler.add_to_queue(queue, sql, (value, self._id))

    def __setitem__(self, column, value):
        r"""Sets the metadata value for the category `column`

        Parameters
        ----------
        column : str
            The column to update
        value : str
            The value to set. This is expected to be a str on the assumption
            that psycopg2 will cast as necessary when updating.

        Raises
        ------
        ValueError
            If the value type does not match the one in the DB
        """
        conn_handler = SQLConnectionHandler()
        queue_name = "set_item_%s" % self._id
        conn_handler.create_queue(queue_name)

        self.add_setitem_queries(column, value, conn_handler, queue_name)

        try:
            conn_handler.execute_queue(queue_name)
        except ValueError as e:
            # catching error so we can check if the error is due to different
            # column type or something else
            type_lookup = defaultdict(lambda: 'varchar')
            type_lookup[int] = 'integer'
            type_lookup[float] = 'float8'
            type_lookup[str] = 'varchar'
            value_type = type_lookup[type(value)]

            sql = """SELECT udt_name
                     FROM information_schema.columns
                     WHERE column_name = %s
                        AND table_schema = 'qiita'
                        AND (table_name = %s OR table_name = %s)"""
            column_type = conn_handler.execute_fetchone(
                sql, (column, self._table, self._dynamic_table))

            if column_type != value_type:
                raise ValueError(
                    'The new value being added to column: "{0}" is "{1}" '
                    '(type: "{2}"). However, this column in the DB is of '
                    'type "{3}". Please change the value in your updated '
                    'template or reprocess your template.'.format(
                        column, value, value_type, column_type))

            raise e

    def __delitem__(self, key):
        r"""Removes the sample with sample id `key` from the database

        Parameters
        ----------
        key : str
            The sample id
        """
        raise QiitaDBNotImplementedError()

    def __iter__(self):
        r"""Iterator over the metadata keys

        Returns
        -------
        Iterator
            Iterator over the sample ids

        See Also
        --------
        keys
        """
        conn_handler = SQLConnectionHandler()
        return iter(self._get_categories(conn_handler))

    def __contains__(self, key):
        r"""Checks if the metadata category `key` is present

        Parameters
        ----------
        key : str
            The sample id

        Returns
        -------
        bool
            True if the metadata category `key` is present, false otherwise
        """
        conn_handler = SQLConnectionHandler()
        return key.lower() in self._get_categories(conn_handler)

    def keys(self):
        r"""Iterator over the metadata categories

        Returns
        -------
        Iterator
            Iterator over the sample ids

        See Also
        --------
        __iter__
        """
        return self.__iter__()

    def values(self):
        r"""Iterator over the metadata values, in metadata category order

        Returns
        -------
        Iterator
            Iterator over metadata values
        """
        d = self._to_dict()
        return d.values()

    def items(self):
        r"""Iterator over (category, value) tuples

        Returns
        -------
        Iterator
            Iterator over (category, value) tuples
        """
        d = self._to_dict()
        return d.items()

    def get(self, key):
        r"""Returns the metadata value for category `key`, or None if the
        category `key` is not present

        Parameters
        ----------
        key : str
            The metadata category

        Returns
        -------
        Obj or None
            The value object for the category `key`, or None if it is not
            present

        See Also
        --------
        __getitem__
        """
        try:
            return self[key]
        except KeyError:
            return None


class MetadataTemplate(QiitaObject):
    r"""Metadata map object that accesses the db to get the sample/prep
    template information

    Attributes
    ----------
    id

    Methods
    -------
    exists
    __len__
    __getitem__
    __setitem__
    __delitem__
    __iter__
    __contains__
    keys
    values
    items
    get
    to_file
    add_filepath
    update

    See Also
    --------
    QiitaObject
    SampleTemplate
    PrepTemplate
    """

    # Used to find the right SQL tables - should be defined on the subclasses
    _table_prefix = None
    _column_table = None
    _id_column = None
    _sample_cls = None

    def _check_id(self, id_):
        r"""Checks that the MetadataTemplate id_ exists on the database"""
        self._check_subclass()

        conn_handler = SQLConnectionHandler()

        return conn_handler.execute_fetchone(
            "SELECT EXISTS(SELECT * FROM qiita.{0} WHERE "
            "{1}=%s)".format(self._table, self._id_column),
            (id_, ))[0]

    @classmethod
    def _table_name(cls, obj_id):
        r"""Returns the dynamic table name

        Parameters
        ----------
        obj_id : int
            The id of the metadata template

        Returns
        -------
        str
            The table name

        Raises
        ------
        IncompetentQiitaDeveloperError
            If called from the base class directly
        """
        if not cls._table_prefix:
            raise IncompetentQiitaDeveloperError(
                "_table_prefix should be defined in the subclasses")
        return "%s%d" % (cls._table_prefix, obj_id)

    @classmethod
    def _clean_validate_template(cls, md_template, study_id, restriction_dict):
        """Takes care of all validation and cleaning of metadata templates

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by sample ids
        study_id : int
            The study to which the metadata template belongs to.
        restriction_dict : dict of {str: Restriction}
            A dictionary with the restrictions that apply to the metadata

        Returns
        -------
        md_template : DataFrame
            Cleaned copy of the input md_template

        Raises
        ------
        QiitaDBColumnError
            If the sample names in md_template contains invalid names
        QiitaDBWarning
            If there are missing columns required for some functionality
        """
        cls._check_subclass()
        invalid_ids = get_invalid_sample_names(md_template.index)
        if invalid_ids:
            raise QiitaDBColumnError("The following sample names in the "
                                     "template contain invalid characters "
                                     "(only alphanumeric characters or periods"
                                     " are allowed): %s." %
                                     ", ".join(invalid_ids))

        # We are going to modify the md_template. We create a copy so
        # we don't modify the user one
        md_template = deepcopy(md_template)

        # Prefix the sample names with the study_id
        prefix_sample_names_with_id(md_template, study_id)

        # In the database, all the column headers are lowercase
        md_template.columns = [c.lower() for c in md_template.columns]

        # Check that we don't have duplicate columns
        if len(set(md_template.columns)) != len(md_template.columns):
            raise QiitaDBDuplicateHeaderError(
                find_duplicates(md_template.columns))

        # Check if we have the columns required for some functionality
        warning_msg = []
        for key, restriction in viewitems(restriction_dict):
            missing = set(restriction.columns).difference(md_template)

            if missing:
                warning_msg.append(
                    "%s: %s" % (restriction.error_msg, ', '.join(missing)))

        if warning_msg:
            warnings.warn(
                "Some functionality will be disabled due to missing "
                "columns:\n\t%s.\nSee the Templates tutorial for a description"
                " of these fields." % ";\n\t".join(warning_msg),
                QiitaDBWarning)

        return md_template

    @classmethod
    def _add_common_creation_steps_to_queue(cls, md_template, obj_id,
                                            conn_handler, queue_name):
        r"""Adds the common creation steps to the queue in conn_handler

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by sample ids
        obj_id : int
            The id of the object being created
        conn_handler : SQLConnectionHandler
            The connection handler object connected to the DB
        queue_name : str
            The queue where the SQL statements will be added
        """
        cls._check_subclass()

        # Get some useful information from the metadata template
        sample_ids = md_template.index.tolist()
        headers = sorted(md_template.keys().tolist())

        # Insert values on template_sample table
        values = [(obj_id, s_id) for s_id in sample_ids]
        sql = "INSERT INTO qiita.{0} ({1}, sample_id) VALUES (%s, %s)".format(
            cls._table, cls._id_column)
        conn_handler.add_to_queue(queue_name, sql, values, many=True)

        # Insert rows on *_columns table
        datatypes = get_datatypes(md_template.ix[:, headers])
        # psycopg2 requires a list of tuples, in which each tuple is a set
        # of values to use in the string formatting of the query. We have all
        # the values in different lists (but in the same order) so use zip
        # to create the list of tuples that psycopg2 requires.
        values = [(obj_id, h, d) for h, d in zip(headers, datatypes)]
        sql = ("INSERT INTO qiita.{0} ({1}, column_name, column_type) "
               "VALUES (%s, %s, %s)").format(cls._column_table, cls._id_column)
        conn_handler.add_to_queue(queue_name, sql, values, many=True)

        # Create table with custom columns
        table_name = cls._table_name(obj_id)
        column_datatype = ["%s %s" % (col, dtype)
                           for col, dtype in zip(headers, datatypes)]
        conn_handler.add_to_queue(
            queue_name,
            "CREATE TABLE qiita.{0} ("
            "sample_id varchar NOT NULL, {1}, "
            "CONSTRAINT fk_{0} FOREIGN KEY (sample_id) "
            "REFERENCES qiita.study_sample (sample_id) "
            "ON UPDATE CASCADE)".format(
                table_name, ', '.join(column_datatype)))

        # Insert values on custom table
        values = as_python_types(md_template, headers)
        values.insert(0, sample_ids)
        values = [v for v in zip(*values)]
        conn_handler.add_to_queue(
            queue_name,
            "INSERT INTO qiita.{0} (sample_id, {1}) "
            "VALUES (%s, {2})".format(table_name, ", ".join(headers),
                                      ', '.join(["%s"] * len(headers))),
            values, many=True)

    def _add_common_extend_steps_to_queue(self, md_template, conn_handler,
                                          queue_name):
        r"""Adds the common extend steps to the queue in conn_handler

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by sample ids
        conn_handler : SQLConnectionHandler
            The connection handler object connected to the DB
        queue_name : str
            The queue where the SQL statements will be added

        Raises
        ------
        QiitaDBError
            If no new samples or new columns are present in `md_template`
        """
        # Check if we are adding new samples
        sample_ids = md_template.index.tolist()
        curr_samples = set(self.keys())
        existing_samples = curr_samples.intersection(sample_ids)
        new_samples = set(sample_ids).difference(existing_samples)

        # Check if we are adding new columns
        headers = md_template.keys().tolist()
        new_cols = set(headers).difference(self.categories())

        if not new_cols and not new_samples:
            raise QiitaDBError(
                "No new samples or new columns found in the template. If you "
                "want to update existing values, you should use the 'update' "
                "functionality.")

        table_name = self._table_name(self._id)
        if new_cols:
            # If we are adding new columns, add them first (simplifies code)
            # Sorting the new columns to enforce an order
            new_cols = sorted(new_cols)
            datatypes = get_datatypes(md_template.ix[:, new_cols])
            sql_cols = """INSERT INTO qiita.{0} ({1}, column_name, column_type)
                          VALUES (%s, %s, %s)""".format(self._column_table,
                                                        self._id_column)
            sql_alter = """ALTER TABLE qiita.{0} ADD COLUMN {1} {2}"""
            for category, dtype in zip(new_cols, datatypes):
                conn_handler.add_to_queue(
                    queue_name, sql_cols, (self._id, category, dtype))
                conn_handler.add_to_queue(
                    queue_name, sql_alter.format(table_name, category, dtype))

            if existing_samples:
                warnings.warn(
                    "No values have been modified for existing samples (%s). "
                    "However, the following columns have been added to them: "
                    "'%s'" % (len(existing_samples), ", ".join(new_cols)),
                    QiitaDBWarning)
                # The values for the new columns are the only ones that get
                # added to the database. None of the existing values will be
                # modified (see update for that functionality)
                min_md_template = md_template[new_cols].loc[existing_samples]
                values = as_python_types(min_md_template, new_cols)
                values.append(existing_samples)
                # psycopg2 requires a list of tuples, in which each tuple is a
                # set of values to use in the string formatting of the query.
                # We have all the values in different lists (but in the same
                # order) so use zip to create the list of tuples that psycopg2
                # requires.
                values = [v for v in zip(*values)]
                set_str = ["{0} = %s".format(col) for col in new_cols]
                sql = """UPDATE qiita.{0}
                         SET {1}
                         WHERE sample_id=%s""".format(table_name,
                                                      ",".join(set_str))
                conn_handler.add_to_queue(queue_name, sql, values, many=True)
        elif existing_samples:
            warnings.warn(
                "%d samples already exist in the template and "
                "their values won't be modified" % len(existing_samples),
                QiitaDBWarning)

        if new_samples:
            new_samples = sorted(new_samples)
            # At this point we only want the information from the new samples
            md_template = md_template.loc[new_samples]

            # Insert values on required columns
            values = [(self._id, s_id) for s_id in new_samples]
            sql = """INSERT INTO qiita.{0} ({1}, sample_id)
                     VALUES (%s, %s)""".format(self._table, self._id_column)
            conn_handler.add_to_queue(queue_name, sql, values, many=True)

            # Insert values on custom table
            values = as_python_types(md_template, headers)
            values.insert(0, new_samples)
            values = [v for v in zip(*values)]
            sql = """INSERT INTO qiita.{0} (sample_id, {1})
                     VALUES (%s, {2})""".format(
                table_name, ", ".join(headers),
                ', '.join(["%s"] * len(headers)))
            conn_handler.add_to_queue(queue_name, sql, values, many=True)

    @classmethod
    def exists(cls, obj_id):
        r"""Checks if already exists a MetadataTemplate for the provided object

        Parameters
        ----------
        obj_id : int
            The id to test if it exists on the database

        Returns
        -------
        bool
            True if already exists. False otherwise.
        """
        cls._check_subclass()
        return exists_table(cls._table_name(obj_id), SQLConnectionHandler())

    def _get_sample_ids(self, conn_handler):
        r"""Returns all the available samples for the metadata template

        Parameters
        ----------
        conn_handler : SQLConnectionHandler
            The connection handler object connected to the DB

        Returns
        -------
        set of str
            The set of all available sample ids
        """
        sample_ids = conn_handler.execute_fetchall(
            "SELECT sample_id FROM qiita.{0} WHERE "
            "{1}=%s".format(self._table, self._id_column),
            (self._id, ))
        return set(sample_id[0] for sample_id in sample_ids)

    def __len__(self):
        r"""Returns the number of samples in the metadata template

        Returns
        -------
        int
            The number of samples in the metadata template
        """
        conn_handler = SQLConnectionHandler()
        return len(self._get_sample_ids(conn_handler))

    def __getitem__(self, key):
        r"""Returns the metadata values for sample id `key`

        Parameters
        ----------
        key : str
            The sample id

        Returns
        -------
        Sample
            The sample object for the sample id `key`

        Raises
        ------
        KeyError
            If the sample id `key` is not present in the metadata template

        See Also
        --------
        get
        """
        if key in self:
            return self._sample_cls(key, self)
        else:
            raise KeyError("Sample id %s does not exists in template %d"
                           % (key, self._id))

    def __setitem__(self, key, value):
        r"""Sets the metadata values for sample id `key`

        Parameters
        ----------
        key : str
            The sample id
        value : Sample
            The sample obj holding the new sample values
        """
        raise QiitaDBNotImplementedError()

    def __delitem__(self, key):
        r"""Removes the sample with sample id `key` from the database

        Parameters
        ----------
        key : str
            The sample id
        """
        raise QiitaDBNotImplementedError()

    def __iter__(self):
        r"""Iterator over the sample ids

        Returns
        -------
        Iterator
            Iterator over the sample ids

        See Also
        --------
        keys
        """
        conn_handler = SQLConnectionHandler()
        return iter(self._get_sample_ids(conn_handler))

    def __contains__(self, key):
        r"""Checks if the sample id `key` is present in the metadata template

        Parameters
        ----------
        key : str
            The sample id

        Returns
        -------
        bool
            True if the sample id `key` is in the metadata template, false
            otherwise
        """
        conn_handler = SQLConnectionHandler()
        return key in self._get_sample_ids(conn_handler)

    def keys(self):
        r"""Iterator over the sorted sample ids

        Returns
        -------
        Iterator
            Iterator over the sample ids

        See Also
        --------
        __iter__
        """
        return self.__iter__()

    def values(self):
        r"""Iterator over the metadata values

        Returns
        -------
        Iterator
            Iterator over Sample obj
        """
        conn_handler = SQLConnectionHandler()
        return iter(self._sample_cls(sample_id, self)
                    for sample_id in self._get_sample_ids(conn_handler))

    def items(self):
        r"""Iterator over (sample_id, values) tuples, in sample id order

        Returns
        -------
        Iterator
            Iterator over (sample_ids, values) tuples
        """
        conn_handler = SQLConnectionHandler()
        return iter((sample_id, self._sample_cls(sample_id, self))
                    for sample_id in self._get_sample_ids(conn_handler))

    def get(self, key):
        r"""Returns the metadata values for sample id `key`, or None if the
        sample id `key` is not present in the metadata map

        Parameters
        ----------
        key : str
            The sample id

        Returns
        -------
        Sample or None
            The sample object for the sample id `key`, or None if it is not
            present

        See Also
        --------
        __getitem__
        """
        try:
            return self[key]
        except KeyError:
            return None

    def _transform_to_dict(self, values):
        r"""Transforms `values` to a dict keyed by sample id

        Parameters
        ----------
        values : object
            The object returned from a execute_fetchall call

        Returns
        -------
        dict
        """
        result = {}
        for row in values:
            # Transform the row to a dictionary
            values_dict = dict(row)
            # Get the sample id of this row
            sid = values_dict['sample_id']
            del values_dict['sample_id']
            # Remove _id_column from this row (if present)
            if self._id_column in values_dict:
                del values_dict[self._id_column]
            result[sid] = values_dict

        return result

    def generate_files(self):
        r"""Generates all the files that contain data from this template

        Raises
        ------
        QiitaDBNotImplementedError
            This method should be implemented by the subclasses
        """
        raise QiitaDBNotImplementedError(
            "generate_files should be implemented in the subclass!")

    def to_file(self, fp, samples=None):
        r"""Writes the MetadataTemplate to the file `fp` in tab-delimited
        format

        Parameters
        ----------
        fp : str
            Path to the output file
        samples : set, optional
            If supplied, only the specified samples will be written to the
            file
        """
        df = self.to_dataframe()
        if samples is not None:
            df = df.loc[samples]

        # Sorting the dataframe so multiple serializations of the metadata
        # template are consistent.
        df.sort_index(axis=0, inplace=True)
        df.sort_index(axis=1, inplace=True)

        # Store the template in a file
        df.to_csv(fp, index_label='sample_name', na_rep="", sep='\t')

    def to_dataframe(self):
        """Returns the metadata template as a dataframe

        Returns
        -------
        pandas DataFrame
            The metadata in the template,indexed on sample id
        """
        conn_handler = SQLConnectionHandler()
        cols = sorted(get_table_cols(self._table_name(self._id)))
        # Get all metadata for the template
        sql = "SELECT {0} FROM qiita.{1}".format(", ".join(cols),
                                                 self._table_name(self.id))
        meta = conn_handler.execute_fetchall(sql, (self._id,))

        # Create the dataframe and clean it up a bit
        df = pd.DataFrame((list(x) for x in meta), columns=cols)
        df.set_index('sample_id', inplace=True, drop=True)

        return df

    def add_filepath(self, filepath, fp_id=None):
        r"""Populates the DB tables for storing the filepath and connects the
        `self` objects with this filepath"""
        # Check that this function has been called from a subclass
        self._check_subclass()

        # Check if the connection handler has been provided. Create a new
        # one if not.
        conn_handler = SQLConnectionHandler()
        fp_id = self._fp_id if fp_id is None else fp_id

        try:
            fpp_id = insert_filepaths([(filepath, fp_id)], None,
                                      "templates", "filepath", conn_handler,
                                      move_files=False)[0]
            values = (self._id, fpp_id)
            conn_handler.execute(
                "INSERT INTO qiita.{0} ({1}, filepath_id) "
                "VALUES (%s, %s)".format(
                    self._filepath_table, self._id_column), values)
        except Exception as e:
            LogEntry.create('Runtime', str(e),
                            info={self.__class__.__name__: self.id})
            raise e

    def get_filepaths(self):
        r"""Retrieves the list of (filepath_id, filepath)"""
        # Check that this function has been called from a subclass
        self._check_subclass()

        # Check if the connection handler has been provided. Create a new
        # one if not.
        conn_handler = SQLConnectionHandler()

        try:
            filepath_ids = conn_handler.execute_fetchall(
                "SELECT filepath_id, filepath FROM qiita.filepath WHERE "
                "filepath_id IN (SELECT filepath_id FROM qiita.{0} WHERE "
                "{1}=%s) ORDER BY filepath_id DESC".format(
                    self._filepath_table, self._id_column),
                (self.id, ))
        except Exception as e:
            LogEntry.create('Runtime', str(e),
                            info={self.__class__.__name__: self.id})
            raise e

        _, fb = get_mountpoint('templates')[0]
        base_fp = partial(join, fb)

        return [(fpid, base_fp(fp)) for fpid, fp in filepath_ids]

    def categories(self):
        """Identifies the metadata columns present in a template

        Returns
        -------
        cols : list
            The static and dynamic category fields

        """
        cols = get_table_cols(self._table_name(self._id))
        cols.remove("sample_id")

        return cols

    def update(self, md_template):
        r"""Update values in the template

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by samples Ids

        Raises
        ------
        QiitaDBError
            If md_template and db do not have the same sample ids
            If md_template and db do not have the same column headers
            If self.can_be_updated is not True
        """
        conn_handler = SQLConnectionHandler()

        # Clean and validate the metadata template given
        new_map = self._clean_validate_template(md_template, self.study_id,
                                                self.columns_restrictions)
        # Retrieving current metadata
        current_map = self._transform_to_dict(conn_handler.execute_fetchall(
            "SELECT * FROM qiita.{0}".format(self._table_name(self.id))))
        current_map = pd.DataFrame.from_dict(current_map, orient='index')

        # simple validations of sample ids and column names
        samples_diff = set(new_map.index).difference(current_map.index)
        if samples_diff:
            raise QiitaDBError('The new template differs from what is stored '
                               'in database by these samples names: %s'
                               % ', '.join(samples_diff))
        columns_diff = set(new_map.columns).difference(current_map.columns)
        if columns_diff:
            raise QiitaDBError('The new template differs from what is stored '
                               'in database by these columns names: %s'
                               % ', '.join(columns_diff))

        # here we are comparing two dataframes following:
        # http://stackoverflow.com/a/17095620/4228285
        current_map.sort(axis=0, inplace=True)
        current_map.sort(axis=1, inplace=True)
        new_map.sort(axis=0, inplace=True)
        new_map.sort(axis=1, inplace=True)
        map_diff = (current_map != new_map).stack()
        map_diff = map_diff[map_diff]
        map_diff.index.names = ['id', 'column']
        changed_cols = map_diff.index.get_level_values('column').unique()

        if not self.can_be_updated(columns=set(changed_cols)):
            raise QiitaDBError('The new template is modifying fields that '
                               'cannot be modified. Try removing the target '
                               'gene fields or deleting the processed data. '
                               'You are trying to modify: %s'
                               % ', '.join(changed_cols))

        for col in changed_cols:
            self.update_category(col, new_map[col].to_dict())

        self.generate_files()

    def update_category(self, category, samples_and_values):
        """Update an existing column

        Parameters
        ----------
        category : str
            The category to update
        samples_and_values : dict
            A mapping of {sample_id: value}

        Raises
        ------
        QiitaDBUnknownIDError
            If a sample_id is included in values that is not in the template
        QiitaDBColumnError
            If the column does not exist in the table. This is implicit, and
            can be thrown by the contained Samples.
        ValueError
            If one of the new values cannot be inserted in the DB due to
            different types
        """
        if not set(self.keys()).issuperset(samples_and_values):
            missing = set(self.keys()) - set(samples_and_values)
            table_name = self._table_name(self._id)
            raise QiitaDBUnknownIDError(missing, table_name)

        conn_handler = SQLConnectionHandler()
        queue_name = "update_category_%s_%s" % (self._id, category)
        conn_handler.create_queue(queue_name)

        for k, v in viewitems(samples_and_values):
            sample = self[k]
            sample.add_setitem_queries(category, v, conn_handler, queue_name)

        try:
            conn_handler.execute_queue(queue_name)
        except ValueError as e:
            # catching error so we can check if the error is due to different
            # column type or something else
            type_lookup = defaultdict(lambda: 'varchar')
            type_lookup[int] = 'integer'
            type_lookup[float] = 'float8'
            type_lookup[str] = 'varchar'
            value_types = set(type_lookup[type(value)]
                              for value in viewvalues(samples_and_values))

            sql = """SELECT udt_name
                     FROM information_schema.columns
                     WHERE column_name = %s
                        AND table_schema = 'qiita'
                        AND (table_name = %s OR table_name = %s)"""
            column_type = conn_handler.execute_fetchone(
                sql, (category, self._table, self._table_name(self._id)))

            if any([column_type != vt for vt in value_types]):
                value_str = ', '.join(
                    [str(value) for value in viewvalues(samples_and_values)])
                value_types_str = ', '.join(value_types)

                raise ValueError(
                    'The new values being added to column: "%s" are "%s" '
                    '(types: "%s"). However, this column in the DB is of '
                    'type "%s". Please change the values in your updated '
                    'template or reprocess your template.'
                    % (category, value_str, value_types_str, column_type))

            raise e

    def check_restrictions(self, restrictions):
        """Checks if the template fulfills the restrictions

        Parameters
        ----------
        restrictions : list of Restriction
            The restrictions to test if the template fulfills

        Returns
        -------
        set of str
            The missing columns
        """
        cols = {col for restriction in restrictions
                for col in restriction.columns}

        return cols.difference(self.categories())
