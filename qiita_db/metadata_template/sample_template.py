# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from __future__ import division
from os.path import join
from time import strftime

from qiita_core.exceptions import IncompetentQiitaDeveloperError
from qiita_db.exceptions import (QiitaDBDuplicateError, QiitaDBError,
                                 QiitaDBUnknownIDError)
from qiita_db.sql_connection import SQLConnectionHandler, Transaction
from qiita_db.util import get_mountpoint, convert_to_id
from qiita_db.study import Study
from qiita_db.data import RawData
from .base_metadata_template import BaseSample, MetadataTemplate
from .prep_template import PrepTemplate
from .constants import SAMPLE_TEMPLATE_COLUMNS


class Sample(BaseSample):
    r"""Class that models a sample present in a SampleTemplate.

    See Also
    --------
    BaseSample
    PrepSample
    """
    _table = "study_sample"
    _table_prefix = "sample_"
    _column_table = "study_sample_columns"
    _id_column = "study_id"

    def _check_template_class(self, md_template):
        r"""Checks that md_template is of the correct type

        Parameters
        ----------
        md_template : SampleTemplate
            The metadata template

        Raises
        ------
        IncompetentQiitaDeveloperError
            If `md_template` is not a SampleTemplate object
        """
        if not isinstance(md_template, SampleTemplate):
            raise IncompetentQiitaDeveloperError()


class SampleTemplate(MetadataTemplate):
    r"""Represent the SampleTemplate of a study. Provides access to the
    tables in the DB that holds the sample metadata information.

    See Also
    --------
    MetadataTemplate
    PrepTemplate
    """
    _table = "study_sample"
    _table_prefix = "sample_"
    _column_table = "study_sample_columns"
    _id_column = "study_id"
    _sample_cls = Sample
    _fp_id = convert_to_id("sample_template", "filepath_type")
    _filepath_table = 'sample_template_filepath'

    @staticmethod
    def metadata_headers():
        """Returns metadata headers available

        Returns
        -------
        list
            Alphabetical list of all metadata headers available
        """
        conn_handler = SQLConnectionHandler()
        return [x[0] for x in
                conn_handler.execute_fetchall(
                "SELECT DISTINCT column_name FROM qiita.study_sample_columns "
                "ORDER BY column_name")]

    @classmethod
    def create(cls, md_template, study):
        r"""Creates the sample template in the database

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by samples Ids
        study : Study
            The study to which the sample template belongs to.
        """
        cls._check_subclass()

        # Check that we don't have a MetadataTemplate for study
        if cls.exists(study.id):
            raise QiitaDBDuplicateError(cls.__name__, 'id: %d' % study.id)

        trans = Transaction("CREATE_SAMPLE_TEMPLATE_%d" % study.id)

        # Clean and validate the metadata template given
        md_template = cls._clean_validate_template(md_template, study.id,
                                                   SAMPLE_TEMPLATE_COLUMNS)

        cls._add_common_creation_steps_to_transaction(md_template, study.id,
                                                      trans)

        trans.execute()

        st = cls(study.id)
        st.generate_files()

        return st

    @classmethod
    def delete(cls, id_):
        r"""Deletes the table from the database

        Parameters
        ----------
        id_ : integer
            The object identifier

        Raises
        ------
        QiitaDBUnknownIDError
            If no sample template with id id_ exists
        QiitaDBError
            If the study that owns this sample template has prep templates
        """
        cls._check_subclass()

        if not cls.exists(id_):
            raise QiitaDBUnknownIDError(id_, cls.__name__)

        trans = Transaction("delete_sample_template_%d" % id_)
        sql = """SELECT EXISTS(SELECT * FROM qiita.study_prep_template
                               WHERE study_id=%s)"""
        args = [id_]
        trans.add(sql, args)
        has_prep_templates = trans.execute(commit=False)[0][0][0]

        if has_prep_templates:
            raise QiitaDBError("Sample template can not be erased because "
                               "there are prep templates associated.")

        table_name = cls._table_name(id_)

        # Delete the sample template filepaths links
        sql = "DELETE FROM qiita.sample_template_filepath WHERE study_id = %s"
        trans.add(sql, args)

        # Delete the dynamic table
        trans.add("DROP TABLE qiita.{0}".format(table_name))

        # Delete the rows from the study_sample table
        sql = "DELETE FROM qiita.{0} WHERE {1} = %s".format(cls._table,
                                                            cls._id_column)
        trans.add(sql, args)

        # Delete the rows from the study_column table
        sql = "DELETE FROM qiita.{0} WHERE {1} = %s".format(cls._column_table,
                                                            cls._id_column)
        trans.add(sql, args)

        trans.execute()

    @property
    def study_id(self):
        """Gets the study id with which this sample template is associated

        Returns
        -------
        int
            The ID of the study with which this sample template is associated
        """
        return self._id

    @property
    def columns_restrictions(self):
        """Gets the dictionary of colums required

        Returns
        -------
        dict
            The dict of restictions
        """
        return SAMPLE_TEMPLATE_COLUMNS

    def can_be_updated(self, **kwargs):
        """Gets if the template can be updated

        Parameters
        ----------
        kwargs : ignored
            Necessary to have in parameters to support other objects.

        Returns
        -------
        bool
            As this is the sample template, it will always return True. See the
            notes.

        Notes
        -----
            The prep template can't be updated in certain situations, see the
            its documentation for more info. However, the sample template
            doesn't have those restrictions. Thus, to be able to use the same
            update code in the base class, we need to have this method and it
            should always return True.
        """
        return True

    def generate_files(self):
        r"""Generates all the files that contain data from this template
        """
        # figuring out the filepath of the sample template
        _id, fp = get_mountpoint('templates')[0]
        fp = join(fp, '%d_%s.txt' % (self.id, strftime("%Y%m%d-%H%M%S")))
        # storing the sample template
        self.to_file(fp)

        # adding the fp to the object
        self.add_filepath(fp)

        # generating all new QIIME mapping files
        for rd_id in Study(self.id).raw_data():
            for pt_id in RawData(rd_id).prep_templates:
                PrepTemplate(pt_id).generate_files()

    def extend(self, md_template):
        """Adds the given sample template to the current one

        Parameters
        ----------
        md_template : DataFrame
            The metadata template file contents indexed by samples Ids
        """
        trans = Transaction("EXTEND_SAMPLE_TEMPLATE_%d" % self.id)

        md_template = self._clean_validate_template(md_template, self.study_id,
                                                    SAMPLE_TEMPLATE_COLUMNS)

        self._add_common_extend_steps_to_transaction(md_template, trans)
        trans.execute()

        self.generate_files()
