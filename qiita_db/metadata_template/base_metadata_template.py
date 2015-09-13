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

import pandas as pd
import numpy as np
from skbio.util import find_duplicates
import warnings

from qiita_core.exceptions import IncompetentQiitaDeveloperError

from qiita_db.exceptions import (QiitaDBUnknownIDError, QiitaDBColumnError,
                                 QiitaDBNotImplementedError, QiitaDBError,
                                 QiitaDBWarning, QiitaDBDuplicateHeaderError,
                                 QiitaDBDuplicateSamplesError)
from qiita_db.base import QiitaObject
from qiita_db.sql_connection import TRN
from qiita_db.util import (exists_table, get_table_cols,
                           get_mountpoint, insert_filepaths)
from qiita_db.logger import LogEntry
from .util import (as_python_types, get_datatypes, get_invalid_sample_names,
                   prefix_sample_names_with_id, type_lookup, cast_to_python)


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
        with TRN:
            cls._check_subclass()
            sql = """SELECT EXISTS(
                        SELECT * FROM qiita.{0}
                        WHERE sample_id=%s AND {1}=%s
                    )""".format(cls._table, cls._id_column)
            TRN.add(sql, [sample_id, md_template.id])
            return TRN.execute_fetchlast()

    def _get_categories(self):
        r"""Returns all the available metadata categories for the sample

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
        with TRN:
            sql = "SELECT * FROM qiita.{0} WHERE sample_id=%s".format(
                self._dynamic_table)
            TRN.add(sql, [self._id])
            d = dict(TRN.execute_fetchindex()[0])

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
        # return the number of columns
        return len(self._get_categories())

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
        with TRN:
            key = key.lower()
            if key not in self._get_categories():
                # The key is not available for the sample, so raise a KeyError
                raise KeyError(
                    "Metadata category %s does not exists for sample %s"
                    " in template %d" % (key, self._id, self._md_template.id))

            sql = """SELECT {0} FROM qiita.{1}
                     WHERE sample_id=%s""".format(key, self._dynamic_table)
            TRN.add(sql, [self._id])
            return TRN.execute_fetchlast()

    def setitem(self, column, value):
        """Sets `value` as value for the given `column`

        Parameters
        ----------
        column : str
            The column to update
        value : str
            The value to set. This is expected to be a str on the assumption
            that psycopg2 will cast as necessary when updating.

        Raises
        ------
        QiitaDBColumnError
            If the column does not exist in the table
        """
        with TRN:
            # Check if the column exist in the table
            if column not in self._get_categories():
                raise QiitaDBColumnError("Column %s does not exist in %s" %
                                         (column, self._dynamic_table))

            sql = """UPDATE qiita.{0}
                     SET {1}=%s
                     WHERE sample_id=%s""".format(self._dynamic_table, column)
            TRN.add(sql, [value, self._id])

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
        with TRN:
            self.setitem(column, value)

            try:
                TRN.execute()
            except ValueError as e:
                # catching error so we can check if the error is due to
                # different column type or something else
                value_type = type_lookup(type(value))

                sql = """SELECT udt_name
                         FROM information_schema.columns
                         WHERE column_name = %s
                            AND table_schema = 'qiita'
                            AND (table_name = %s OR table_name = %s)"""
                TRN.add(sql, [column, self._table, self._dynamic_table])
                column_type = TRN.execute_fetchlast()

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
        return iter(self._get_categories())

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
        return key.lower() in self._get_categories()

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
        with TRN:
            sql = "SELECT EXISTS(SELECT * FROM qiita.{0} WHERE {1}=%s)".format(
                self._table, self._id_column)
            TRN.add(sql, [id_])
            return TRN.execute_fetchlast()

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

        if len(set(md_template.index)) != len(md_template.index):
            raise QiitaDBDuplicateSamplesError(
                find_duplicates(md_template.index))

        # We are going to modify the md_template. We create a copy so
        # we don't modify the user one
        md_template = md_template.copy(deep=True)

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
    def _common_creation_steps(cls, md_template, obj_id):
        r"""Executes the common creation steps

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by sample ids
        obj_id : int
            The id of the object being created
        """
        with TRN:
            cls._check_subclass()

            # Get some useful information from the metadata template
            sample_ids = md_template.index.tolist()
            headers = sorted(md_template.keys().tolist())

            # Insert values on template_sample table
            values = [[obj_id, s_id] for s_id in sample_ids]
            sql = """INSERT INTO qiita.{0} ({1}, sample_id)
                     VALUES (%s, %s)""".format(cls._table, cls._id_column)
            TRN.add(sql, values, many=True)

            # Insert rows on *_columns table
            datatypes = get_datatypes(md_template.ix[:, headers])
            # psycopg2 requires a list of tuples, in which each tuple is a set
            # of values to use in the string formatting of the query. We have
            # all the values in different lists (but in the same order) so use
            # zip to create the list of tuples that psycopg2 requires.
            values = [[obj_id, h, d] for h, d in zip(headers, datatypes)]
            sql = """INSERT INTO qiita.{0} ({1}, column_name, column_type)
                     VALUES (%s, %s, %s)""".format(cls._column_table,
                                                   cls._id_column)
            TRN.add(sql, values, many=True)

            # Create table with custom columns
            table_name = cls._table_name(obj_id)
            column_datatype = ["%s %s" % (col, dtype)
                               for col, dtype in zip(headers, datatypes)]
            sql = """CREATE TABLE qiita.{0} (
                        sample_id varchar NOT NULL, {1},
                        CONSTRAINT fk_{0} FOREIGN KEY (sample_id)
                            REFERENCES qiita.study_sample (sample_id)
                            ON UPDATE CASCADE
                     )""".format(table_name, ', '.join(column_datatype))
            TRN.add(sql)

            # Insert values on custom table
            values = as_python_types(md_template, headers)
            values.insert(0, sample_ids)
            values = [list(v) for v in zip(*values)]
            sql = """INSERT INTO qiita.{0} (sample_id, {1})
                     VALUES (%s, {2})""".format(
                table_name, ", ".join(headers),
                ', '.join(["%s"] * len(headers)))
            TRN.add(sql, values, many=True)

            # Execute all the steps
            TRN.execute()

    def can_be_extended(self, new_samples, new_cols):
        """Whether the template can be updated or not

        Parameters
        ----------
        new_samples : list of str
            The new samples to be added
        new_cols : list of str
            The new columns to be added

        Returns
        -------
        bool
            Whether the template can be extended or not
        str
            The error message in case that it can't be extended

        Raises
        ------
        QiitaDBNotImplementedError
            This method should be implemented in the subclasses
        """
        raise QiitaDBNotImplementedError(
            "The method 'can_be_extended' should be implemented in "
            "the subclasses")

    def can_be_updated(self, **kwargs):
        """Whether the template can be updated or not

        Returns
        -------
        bool
            Whether the template can be updated or not

        Raises
        ------
        QiitaDBNotImplementedError
            This method should be implemented in the subclasses
        """
        raise QiitaDBNotImplementedError(
            "The method 'can_be_updated' should be implemented in "
            "the subclasses")

    def _common_extend_steps(self, md_template):
        r"""executes the common extend steps

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by sample ids
        """
        with TRN:
            # Check if we are adding new samples
            sample_ids = md_template.index.tolist()
            curr_samples = set(self.keys())
            existing_samples = curr_samples.intersection(sample_ids)
            new_samples = set(sample_ids).difference(existing_samples)

            # Check if we are adding new columns
            headers = md_template.keys().tolist()
            new_cols = set(headers).difference(self.categories())

            if not new_cols and not new_samples:
                return

            is_extendable, error_msg = self.can_be_extended(new_samples,
                                                            new_cols)

            if not is_extendable:
                raise QiitaDBError(error_msg)

            table_name = self._table_name(self._id)
            if new_cols:
                warnings.warn(
                    "The following columns have been added to the existing"
                    " template: %s" % ", ".join(new_cols),
                    QiitaDBWarning)
                # If we are adding new columns, add them first (simplifies
                # code). Sorting the new columns to enforce an order
                new_cols = sorted(new_cols)
                datatypes = get_datatypes(md_template.ix[:, new_cols])
                sql_cols = """INSERT INTO qiita.{0}
                                    ({1}, column_name, column_type)
                              VALUES (%s, %s, %s)""".format(self._column_table,
                                                            self._id_column)
                sql_alter = """ALTER TABLE qiita.{0} ADD COLUMN {1} {2}"""
                for category, dtype in zip(new_cols, datatypes):
                    TRN.add(sql_cols, [self._id, category, dtype])
                    TRN.add(sql_alter.format(table_name, category, dtype))

                if existing_samples:
                    # The values for the new columns are the only ones that get
                    # added to the database. None of the existing values will
                    # be modified (see update for that functionality)
                    min_md_template = \
                        md_template[new_cols].loc[existing_samples]
                    values = as_python_types(min_md_template, new_cols)
                    values.append(existing_samples)
                    # psycopg2 requires a list of iterable, in which each
                    # iterable is a set of values to use in the string
                    # formatting of the query. We have all the values in
                    # different lists (but in the same order) so use zip to
                    # create the list of iterable that psycopg2 requires.
                    values = [list(v) for v in zip(*values)]
                    set_str = ["{0} = %s".format(col) for col in new_cols]
                    sql = """UPDATE qiita.{0}
                             SET {1}
                             WHERE sample_id=%s""".format(table_name,
                                                          ",".join(set_str))
                    TRN.add(sql, values, many=True)

            if new_samples:
                warnings.warn(
                    "The following samples have been added to the existing"
                    " template: %s" % ", ".join(new_samples),
                    QiitaDBWarning)
                new_samples = sorted(new_samples)
                # At this point we only want the information
                # from the new samples
                md_template = md_template.loc[new_samples]

                # Insert values on required columns
                values = [[self._id, s_id] for s_id in new_samples]
                sql = """INSERT INTO qiita.{0} ({1}, sample_id)
                         VALUES (%s, %s)""".format(self._table,
                                                   self._id_column)
                TRN.add(sql, values, many=True)

                # Insert values on custom table
                values = as_python_types(md_template, headers)
                values.insert(0, new_samples)
                values = [list(v) for v in zip(*values)]
                sql = """INSERT INTO qiita.{0} (sample_id, {1})
                         VALUES (%s, {2})""".format(
                    table_name, ", ".join(headers),
                    ', '.join(["%s"] * len(headers)))
                TRN.add(sql, values, many=True)

            # Execute all the steps
            TRN.execute()

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
        return exists_table(cls._table_name(obj_id))

    def _get_sample_ids(self):
        r"""Returns all the available samples for the metadata template

        Returns
        -------
        set of str
            The set of all available sample ids
        """
        with TRN:
            sql = "SELECT sample_id FROM qiita.{0} WHERE {1}=%s".format(
                self._table, self._id_column)
            TRN.add(sql, [self._id])
            return set(TRN.execute_fetchflatten())

    def __len__(self):
        r"""Returns the number of samples in the metadata template

        Returns
        -------
        int
            The number of samples in the metadata template
        """
        return len(self._get_sample_ids())

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
        with TRN:
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
        return iter(self._get_sample_ids())

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
        return key in self._get_sample_ids()

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
        with TRN:
            return iter(self._sample_cls(sample_id, self)
                        for sample_id in self._get_sample_ids())

    def items(self):
        r"""Iterator over (sample_id, values) tuples, in sample id order

        Returns
        -------
        Iterator
            Iterator over (sample_ids, values) tuples
        """
        with TRN:
            return iter((sample_id, self._sample_cls(sample_id, self))
                        for sample_id in self._get_sample_ids())

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
        with TRN:
            df = self.to_dataframe()
            if samples is not None:
                df = df.loc[samples]

            # Sorting the dataframe so multiple serializations of the metadata
            # template are consistent.
            df.sort_index(axis=0, inplace=True)
            df.sort_index(axis=1, inplace=True)

            # Store the template in a file
            df.to_csv(fp, index_label='sample_name', na_rep="", sep='\t',
                      encoding='utf-8')

    def to_dataframe(self):
        """Returns the metadata template as a dataframe

        Returns
        -------
        pandas DataFrame
            The metadata in the template,indexed on sample id
        """
        with TRN:
            cols = sorted(get_table_cols(self._table_name(self._id)))
            # Get all metadata for the template
            sql = "SELECT {0} FROM qiita.{1}".format(", ".join(cols),
                                                     self._table_name(self.id))
            TRN.add(sql, [self._id])
            meta = TRN.execute_fetchindex()

            # Create the dataframe and clean it up a bit
            df = pd.DataFrame((list(x) for x in meta), columns=cols)
            df.set_index('sample_id', inplace=True, drop=True)

            return df

    def add_filepath(self, filepath, fp_id=None):
        r"""Populates the DB tables for storing the filepath and connects the
        `self` objects with this filepath"""
        with TRN:
            fp_id = self._fp_id if fp_id is None else fp_id

            try:
                fpp_id = insert_filepaths([(filepath, fp_id)], None,
                                          "templates", "filepath",
                                          move_files=False)[0]
                sql = """INSERT INTO qiita.{0} ({1}, filepath_id)
                         VALUES (%s, %s)""".format(self._filepath_table,
                                                   self._id_column)
                TRN.add(sql, [self._id, fpp_id])
                TRN.execute()
            except Exception as e:
                LogEntry.create('Runtime', str(e),
                                info={self.__class__.__name__: self.id})
                raise e

    def get_filepaths(self):
        r"""Retrieves the list of (filepath_id, filepath)"""
        with TRN:
            try:
                sql = """SELECT filepath_id, filepath
                         FROM qiita.filepath
                         WHERE filepath_id IN (
                            SELECT filepath_id FROM qiita.{0}
                            WHERE {1}=%s)
                         ORDER BY filepath_id DESC""".format(
                    self._filepath_table, self._id_column)

                TRN.add(sql, [self.id])
                filepath_ids = TRN.execute_fetchindex()
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

    def extend(self, md_template):
        """Adds the given template to the current one

        Parameters
        ----------
        md_template : DataFrame
            The metadata template contents indexed by sample ids
        """
        with TRN:
            md_template = self._clean_validate_template(
                md_template, self.study_id, self.columns_restrictions)
            self._common_extend_steps(md_template)
            self.generate_files()

    def update(self, md_template):
        r"""Update values in the template

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by samples ids

        Raises
        ------
        QiitaDBError
            If md_template and db do not have the same sample ids
            If md_template and db do not have the same column headers
            If self.can_be_updated is not True
        QiitaDBWarning
            If there are no differences between the contents of the DB and the
            passed md_template
        """
        with TRN:
            # Clean and validate the metadata template given
            new_map = self._clean_validate_template(md_template, self.study_id,
                                                    self.columns_restrictions)
            # Retrieving current metadata
            current_map = self.to_dataframe()

            # simple validations of sample ids and column names
            samples_diff = set(new_map.index).difference(current_map.index)
            if samples_diff:
                raise QiitaDBError(
                    'The new template differs from what is stored '
                    'in database by these samples names: %s'
                    % ', '.join(samples_diff))

            if not set(current_map.columns).issuperset(new_map.columns):
                columns_diff = set(new_map.columns).difference(
                    current_map.columns)
                raise QiitaDBError(
                    'Some of the columns in your template are not present in '
                    'the system. Use "extend" if you want to add more columns '
                    'to the template. Missing columns: %s'
                    % ', '.join(columns_diff))

            # In order to speed up some computation, let's compare only the
            # common columns. current_map.columns is a superset of
            # new_map.columns, so this will not fail
            current_map = current_map[new_map.columns]

            # Get the values that we need to change
            # diff_map is a DataFrame that hold boolean values. If a cell is
            # True, means that the new_map is different from the current_map
            # while False means that the cell has the same value
            # In order to compare them, they've to be identically labeled, so
            # we need to sort the 'index' axis to be identically labeled. The
            # 'column' axis is already the same given the previous line of code
            current_map.sort_index(axis='index', inplace=True)
            new_map.sort_index(axis='index', inplace=True)
            diff_map = current_map != new_map
            # ne_stacked holds a MultiIndexed DataFrame in which the first
            # level of indexing is the sample_name and the second one is the
            # columns. We only have 1 column, which holds if that
            # (sample, column) pair has been modified or not (i.e. cell)
            ne_stacked = diff_map.stack()
            # by using ne_stacked to index himself, we get only the columns
            # that did change (see boolean indexing in pandas docs)
            changed = ne_stacked[ne_stacked]
            if changed.empty:
                warnings.warn(
                    "There are no differences between the data stored in the "
                    "DB and the new data provided",
                    QiitaDBWarning)
            changed.index.names = ['sample_name', 'column']
            # the combination of np.where and boolean indexing produces
            # a numpy array with only the values that actually changed
            # between the current_map and new_map
            changed_to = new_map.values[np.where(diff_map)]

            # to_update is a MultiIndexed DataFrame, in which the index 0 is
            # the samples and the index 1 is the columns, we define these
            # variables here so we don't put magic numbers across the code
            sample_idx = 0
            col_idx = 1
            to_update = pd.DataFrame({'to': changed_to}, index=changed.index)

            # Get the columns that we need to change
            indices = list(set(to_update.index.labels[col_idx]))
            cols_to_update = to_update.index.levels[col_idx][indices]

            if not self.can_be_updated(columns=set(cols_to_update)):
                raise QiitaDBError(
                    'The new template is modifying fields that cannot be '
                    'modified. Try removing the restricted fields or '
                    'deleting the processed data. You are trying to modify: %s'
                    % ', '.join(cols_to_update))

            # Get the samples that we need to change
            indices = list(set(to_update.index.labels[sample_idx]))
            samples_to_update = to_update.index.levels[sample_idx][indices]

            sql_eq_cols = ', '.join(
                ["{0} = c.{0}".format(col) for col in cols_to_update])
            # We add 1 because we need to add the sample name
            single_value = "(%s)" % ', '.join(
                ["%s"] * (len(cols_to_update) + 1))
            sql_values = ', '.join([single_value] * len(samples_to_update))
            sql_cols = ', '.join(cols_to_update)

            sql = """UPDATE qiita.{0} AS t SET
                        {1}
                     FROM (VALUES {2})
                        AS c(sample_id, {3})
                     WHERE c.sample_id = t.sample_id
                    """.format(self._table_name(self._id), sql_eq_cols,
                               sql_values, sql_cols)
            sql_args = []
            for sample in samples_to_update:
                sample_vals = [cast_to_python(new_map[col][sample])
                               for col in cols_to_update]
                sample_vals.insert(0, sample)
                sql_args.extend(sample_vals)

            TRN.add(sql, sql_args)
            TRN.execute()

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
        with TRN:
            if not set(self.keys()).issuperset(samples_and_values):
                missing = set(self.keys()) - set(samples_and_values)
                table_name = self._table_name(self._id)
                raise QiitaDBUnknownIDError(missing, table_name)

            for k, v in viewitems(samples_and_values):
                sample = self[k]
                if isinstance(v, np.generic):
                    v = np.asscalar(v)
                sample.setitem(category, v)

            try:
                TRN.execute()
            except ValueError as e:
                # catching error so we can check if the error is due to
                # different column type or something else

                value_types = set(type_lookup(type(value))
                                  for value in viewvalues(samples_and_values))

                sql = """SELECT udt_name
                         FROM information_schema.columns
                         WHERE column_name = %s
                            AND table_schema = 'qiita'
                            AND (table_name = %s OR table_name = %s)"""
                TRN.add(sql,
                        [category, self._table, self._table_name(self._id)])
                column_type = TRN.execute_fetchlast()

                if any([column_type != vt for vt in value_types]):
                    value_str = ', '.join(
                        [str(value)
                         for value in viewvalues(samples_and_values)])
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
