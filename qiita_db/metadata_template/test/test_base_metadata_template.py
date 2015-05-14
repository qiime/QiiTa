# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main

from qiita_core.exceptions import IncompetentQiitaDeveloperError
from qiita_db.study import Study
from qiita_db.metadata_template.base_metadata_template import (
    MetadataTemplate, BaseSample)
from qiita_db.metadata_template.sample_template import SampleTemplate


class TestBaseSample(TestCase):
    """Tests the BaseSample class"""

    def test_init(self):
        """BaseSample init should raise an error (it's a base class)"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            BaseSample('SKM7.640188', SampleTemplate(1))

    def test_exists(self):
        """exists should raise an error if called from the base class"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            BaseSample.exists('SKM7.640188', SampleTemplate(1))


class TestMetadataTemplateReadOnly(TestCase):
    """Tests the MetadataTemplate base class"""
    def setUp(self):
        self.study = Study(1)

    def test_init(self):
        """Init raises an error because it's not called from a subclass"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            MetadataTemplate(1)

    def test_exist(self):
        """Exists raises an error because it's not called from a subclass"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            MetadataTemplate.exists(self.study)

    def test_table_name(self):
        """table name raises an error because it's not called from a subclass
        """
        with self.assertRaises(IncompetentQiitaDeveloperError):
            MetadataTemplate._table_name(self.study)

    def test_add_common_creation_steps_to_queue(self):
        """_add_common_creation_steps_to_queue raises an error from base class
        """
        with self.assertRaises(IncompetentQiitaDeveloperError):
            MetadataTemplate._add_common_creation_steps_to_queue(
                None, 1, None, "")

    def test_clean_validate_template(self):
        """_clean_validate_template raises an error from base class"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            MetadataTemplate._clean_validate_template(None, 1, None)


if __name__ == '__main__':
    main()
