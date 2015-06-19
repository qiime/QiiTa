# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from future.builtins import zip
from unittest import TestCase, main
from datetime import datetime
from tempfile import mkstemp
from os import close, remove
from collections import Iterable

import numpy.testing as npt
import pandas as pd
from pandas.util.testing import assert_frame_equal

from qiita_core.util import qiita_test_checker
from qiita_core.exceptions import IncompetentQiitaDeveloperError
from qiita_db.exceptions import (QiitaDBDuplicateError, QiitaDBUnknownIDError,
                                 QiitaDBNotImplementedError,
                                 QiitaDBDuplicateHeaderError,
                                 QiitaDBColumnError, QiitaDBError,
                                 QiitaDBWarning)
from qiita_db.sql_connection import SQLConnectionHandler
from qiita_db.study import Study, StudyPerson
from qiita_db.user import User
from qiita_db.util import exists_table, get_count
from qiita_db.metadata_template.sample_template import SampleTemplate, Sample
from qiita_db.metadata_template.prep_template import PrepTemplate, PrepSample
from qiita_db.metadata_template.constants import SAMPLE_TEMPLATE_COLUMNS


class BaseTestSample(TestCase):
    def setUp(self):
        self.sample_template = SampleTemplate(1)
        self.sample_id = '1.SKB8.640193'
        self.tester = Sample(self.sample_id, self.sample_template)
        self.exp_categories = {'physical_specimen_location',
                               'physical_specimen_remaining',
                               'dna_extracted', 'sample_type',
                               'collection_timestamp', 'host_subject_id',
                               'description', 'season_environment',
                               'assigned_from_geo', 'texture', 'taxon_id',
                               'depth', 'host_taxid', 'common_name',
                               'water_content_soil', 'elevation', 'temp',
                               'tot_nitro', 'samp_salinity', 'altitude',
                               'env_biome', 'country', 'ph', 'anonymized_name',
                               'tot_org_carb', 'description_duplicate',
                               'env_feature', 'latitude', 'longitude'}


class TestSampleReadOnly(BaseTestSample):
    def test_add_setitem_queries_error(self):
        conn_handler = SQLConnectionHandler()
        queue = "test_queue"
        conn_handler.create_queue(queue)

        with self.assertRaises(QiitaDBColumnError):
            self.tester.add_setitem_queries(
                'COL_DOES_NOT_EXIST', 0.30, conn_handler, queue)

    def test_add_setitem_queries_required(self):
        conn_handler = SQLConnectionHandler()
        queue = "test_queue"
        conn_handler.create_queue(queue)

        self.tester.add_setitem_queries(
            'physical_specimen_remaining', True, conn_handler, queue)

        obs = conn_handler.queues[queue]
        sql = """UPDATE qiita.sample_1
                 SET physical_specimen_remaining=%s
                 WHERE sample_id=%s"""
        exp = [(sql, (True, '1.SKB8.640193'))]
        self.assertEqual(obs, exp)

    def test_add_setitem_queries_dynamic(self):
        conn_handler = SQLConnectionHandler()
        queue = "test_queue"
        conn_handler.create_queue(queue)

        self.tester.add_setitem_queries(
            'tot_nitro', '1234.5', conn_handler, queue)

        obs = conn_handler.queues[queue]
        sql = """UPDATE qiita.sample_1
                 SET tot_nitro=%s
                 WHERE sample_id=%s"""
        exp = [(sql, ('1234.5', '1.SKB8.640193'))]
        self.assertEqual(obs, exp)

    def test_init_unknown_error(self):
        """Init raises an error if the sample id is not found in the template
        """
        with self.assertRaises(QiitaDBUnknownIDError):
            Sample('Not_a_Sample', self.sample_template)

    def test_init_wrong_template(self):
        """Raises an error if using a PrepTemplate instead of SampleTemplate"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            Sample('SKB8.640193', PrepTemplate(1))

    def test_init(self):
        """Init correctly initializes the sample object"""
        sample = Sample(self.sample_id, self.sample_template)
        # Check that the internal id have been correctly set
        self.assertEqual(sample._id, '1.SKB8.640193')
        # Check that the internal template have been correctly set
        self.assertEqual(sample._md_template, self.sample_template)
        # Check that the internal dynamic table name have been correctly set
        self.assertEqual(sample._dynamic_table, "sample_1")

    def test_eq_true(self):
        """Equality correctly returns true"""
        other = Sample(self.sample_id, self.sample_template)
        self.assertTrue(self.tester == other)

    def test_eq_false_type(self):
        """Equality returns false if types are not equal"""
        other = PrepSample(self.sample_id, PrepTemplate(1))
        self.assertFalse(self.tester == other)

    def test_eq_false_id(self):
        """Equality returns false if ids are different"""
        other = Sample('1.SKD8.640184', self.sample_template)
        self.assertFalse(self.tester == other)

    def test_exists_true(self):
        """Exists returns true if the sample exists"""
        self.assertTrue(Sample.exists(self.sample_id, self.sample_template))

    def test_exists_false(self):
        """Exists returns false if the sample does not exists"""
        self.assertFalse(Sample.exists('Not_a_Sample', self.sample_template))

    def test_get_categories(self):
        """Correctly returns the set of category headers"""
        conn_handler = SQLConnectionHandler()
        obs = self.tester._get_categories(conn_handler)
        self.assertEqual(obs, self.exp_categories)

    def test_len(self):
        """Len returns the correct number of categories"""
        self.assertEqual(len(self.tester), 29)

    def test_getitem_required(self):
        """Get item returns the correct metadata value from the required table
        """
        self.assertEqual(self.tester['physical_specimen_location'], 'ANL')
        self.assertEqual(self.tester['collection_timestamp'],
                         datetime(2011, 11, 11, 13, 00, 00))
        self.assertTrue(self.tester['dna_extracted'])

    def test_getitem_dynamic(self):
        """Get item returns the correct metadata value from the dynamic table
        """
        self.assertEqual(self.tester['SEASON_ENVIRONMENT'], 'winter')
        self.assertEqual(self.tester['depth'], 0.15)

    def test_getitem_error(self):
        """Get item raises an error if category does not exists"""
        with self.assertRaises(KeyError):
            self.tester['Not_a_Category']

    def test_iter(self):
        """iter returns an iterator over the category headers"""
        obs = self.tester.__iter__()
        self.assertTrue(isinstance(obs, Iterable))
        self.assertEqual(set(obs), self.exp_categories)

    def test_contains_true(self):
        """contains returns true if the category header exists"""
        self.assertTrue('DEPTH' in self.tester)
        self.assertTrue('depth' in self.tester)

    def test_contains_false(self):
        """contains returns false if the category header does not exists"""
        self.assertFalse('Not_a_Category' in self.tester)

    def test_keys(self):
        """keys returns an iterator over the metadata headers"""
        obs = self.tester.keys()
        self.assertTrue(isinstance(obs, Iterable))
        self.assertEqual(set(obs), self.exp_categories)

    def test_values(self):
        """values returns an iterator over the values"""
        obs = self.tester.values()
        self.assertTrue(isinstance(obs, Iterable))
        exp = {'ANL', True, True, 'ENVO:soil',
               datetime(2011, 11, 11, 13, 00, 00), '1001:M7',
               'Cannabis Soil Microbiome', 'winter', 'n',
               '64.6 sand, 17.6 silt, 17.8 clay', '1118232', 0.15, '3483',
               'root metagenome', 0.164, 114, 15, 1.41, 7.15, 0,
               'ENVO:Temperate grasslands, savannas, and shrubland biome',
               'GAZ:United States of America', 6.94, 'SKB8', 5,
               'Burmese root', 'ENVO:plant-associated habitat', 74.0894932572,
               65.3283470202}
        self.assertEqual(set(obs), exp)

    def test_items(self):
        """items returns an iterator over the (key, value) tuples"""
        obs = self.tester.items()
        self.assertTrue(isinstance(obs, Iterable))
        exp = {('physical_specimen_location', 'ANL'),
               ('physical_specimen_remaining', True),
               ('dna_extracted', True),
               ('sample_type', 'ENVO:soil'),
               ('collection_timestamp', datetime(2011, 11, 11, 13, 00, 00)),
               ('host_subject_id', '1001:M7'),
               ('description', 'Cannabis Soil Microbiome'),
               ('season_environment', 'winter'), ('assigned_from_geo', 'n'),
               ('texture', '64.6 sand, 17.6 silt, 17.8 clay'),
               ('taxon_id', '1118232'), ('depth', 0.15),
               ('host_taxid', '3483'), ('common_name', 'root metagenome'),
               ('water_content_soil', 0.164), ('elevation', 114), ('temp', 15),
               ('tot_nitro', 1.41), ('samp_salinity', 7.15), ('altitude', 0),
               ('env_biome',
                'ENVO:Temperate grasslands, savannas, and shrubland biome'),
               ('country', 'GAZ:United States of America'), ('ph', 6.94),
               ('anonymized_name', 'SKB8'), ('tot_org_carb', 5),
               ('description_duplicate', 'Burmese root'),
               ('env_feature', 'ENVO:plant-associated habitat'),
               ('latitude', 74.0894932572),
               ('longitude', 65.3283470202)}
        self.assertEqual(set(obs), exp)

    def test_get(self):
        """get returns the correct sample object"""
        self.assertEqual(self.tester.get('SEASON_ENVIRONMENT'), 'winter')
        self.assertEqual(self.tester.get('depth'), 0.15)

    def test_get_none(self):
        """get returns none if the sample id is not present"""
        self.assertTrue(self.tester.get('Not_a_Category') is None)

    def test_columns_restrictions(self):
        """that it returns SAMPLE_TEMPLATE_COLUMNS"""
        self.assertEqual(self.sample_template.columns_restrictions,
                         SAMPLE_TEMPLATE_COLUMNS)

    def test_can_be_updated(self):
        """test if the template can be updated"""
        self.assertTrue(self.sample_template.can_be_updated)


@qiita_test_checker()
class TestSampleReadWrite(BaseTestSample):
    def test_setitem(self):
        with self.assertRaises(QiitaDBColumnError):
            self.tester['column that does not exist'] = 0.30

        with self.assertRaises(ValueError):
            self.tester['collection_timestamp'] = "Error!"

        self.assertEqual(self.tester['tot_nitro'], 1.41)
        self.tester['tot_nitro'] = '1234.5'
        self.assertEqual(self.tester['tot_nitro'], 1234.5)

    def test_delitem(self):
        """delitem raises an error (currently not allowed)"""
        with self.assertRaises(QiitaDBNotImplementedError):
            del self.tester['DEPTH']


class BaseTestSampleTemplate(TestCase):
    def _set_up(self):
        self.metadata_dict = {
            'Sample1': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 1',
                        'str_column': 'Value for sample 1',
                        'int_column': 1,
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample2': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'int_column': 2,
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 2',
                        'str_column': 'Value for sample 2',
                        'latitude': 4.2,
                        'longitude': 1.1,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample3': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 3',
                        'str_column': 'Value for sample 3',
                        'int_column': 3,
                        'latitude': 4.8,
                        'longitude': 4.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            }
        self.metadata = pd.DataFrame.from_dict(self.metadata_dict,
                                               orient='index')

        metadata_str_prefix_dict = {
            'foo.Sample1': self.metadata_dict['Sample1'],
            'bar.Sample2': self.metadata_dict['Sample2'],
            'foo.Sample3': self.metadata_dict['Sample3'],
        }
        self.metadata_str_prefix = pd.DataFrame.from_dict(
            metadata_str_prefix_dict, orient='index')

        metadata_int_prefix_dict = {
            '12.Sample1': self.metadata_dict['Sample1'],
            '12.Sample2': self.metadata_dict['Sample2'],
            '12.Sample3': self.metadata_dict['Sample3']
        }
        self.metadata_int_pref = pd.DataFrame.from_dict(
            metadata_int_prefix_dict, orient='index')

        metadata_prefixed_dict = {
            '2.Sample1': self.metadata_dict['Sample1'],
            '2.Sample2': self.metadata_dict['Sample2'],
            '2.Sample3': self.metadata_dict['Sample3']
        }
        self.metadata_prefixed = pd.DataFrame.from_dict(
            metadata_prefixed_dict, orient='index')

        self.test_study = Study(1)
        self.tester = SampleTemplate(1)
        self.exp_sample_ids = {
            '1.SKB1.640202', '1.SKB2.640194', '1.SKB3.640195', '1.SKB4.640189',
            '1.SKB5.640181', '1.SKB6.640176', '1.SKB7.640196', '1.SKB8.640193',
            '1.SKB9.640200', '1.SKD1.640179', '1.SKD2.640178', '1.SKD3.640198',
            '1.SKD4.640185', '1.SKD5.640186', '1.SKD6.640190', '1.SKD7.640191',
            '1.SKD8.640184', '1.SKD9.640182', '1.SKM1.640183', '1.SKM2.640199',
            '1.SKM3.640197', '1.SKM4.640180', '1.SKM5.640177', '1.SKM6.640187',
            '1.SKM7.640188', '1.SKM8.640201', '1.SKM9.640192'}
        self._clean_up_files = []

        self.metadata_dict_updated_dict = {
            'Sample1': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '6',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 1',
                        'str_column': 'Value for sample 1',
                        'int_column': 1,
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample2': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '5',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'the only one',
                        'Description': 'Test Sample 2',
                        'str_column': 'Value for sample 2',
                        'int_column': 2,
                        'latitude': 4.2,
                        'longitude': 1.1,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample3': {'physical_specimen_location': 'new location',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '10',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 3',
                        'str_column': 'Value for sample 3',
                        'int_column': 3,
                        'latitude': 4.8,
                        'longitude': 4.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            }
        self.metadata_dict_updated = pd.DataFrame.from_dict(
            self.metadata_dict_updated_dict, orient='index')

        metadata_dict_updated_sample_error = {
            'Sample1': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '6',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 1',
                        'str_column': 'Value for sample 1',
                        'int_column': 1,
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample2': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '5',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'the only one',
                        'Description': 'Test Sample 2',
                        'str_column': 'Value for sample 2',
                        'int_column': 2,
                        'latitude': 4.2,
                        'longitude': 1.1,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample3': {'physical_specimen_location': 'new location',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '10',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 3',
                        'str_column': 'Value for sample 3',
                        'int_column': 3,
                        'latitude': 4.8,
                        'longitude': 4.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample4': {'physical_specimen_location': 'new location',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '10',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 4',
                        'str_column': 'Value for sample 4',
                        'int_column': 4,
                        'latitude': 4.8,
                        'longitude': 4.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'}
            }
        self.metadata_dict_updated_sample_error = pd.DataFrame.from_dict(
            metadata_dict_updated_sample_error, orient='index')

        metadata_dict_updated_column_error = {
            'Sample1': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '6',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 1',
                        'str_column': 'Value for sample 1',
                        'int_column': 1,
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens',
                        'extra_col': True},
            'Sample2': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '5',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'the only one',
                        'Description': 'Test Sample 2',
                        'str_column': 'Value for sample 2',
                        'int_column': 2,
                        'latitude': 4.2,
                        'longitude': 1.1,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens',
                        'extra_col': True},
            'Sample3': {'physical_specimen_location': 'new location',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': '10',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 3',
                        'str_column': 'Value for sample 3',
                        'int_column': 3,
                        'latitude': 4.8,
                        'longitude': 4.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens',
                        'extra_col': True},
            }
        self.metadata_dict_updated_column_error = pd.DataFrame.from_dict(
            metadata_dict_updated_column_error, orient='index')

    def tearDown(self):
        for f in self._clean_up_files:
            remove(f)


class TestSampleTemplateReadOnly(BaseTestSampleTemplate):
    def setUp(self):
        self._set_up()

    def test_metadata_headers(self):
        obs = SampleTemplate.metadata_headers()
        exp = {'physical_specimen_location', 'physical_specimen_remaining',
               'dna_extracted', 'sample_type', 'collection_timestamp',
               'host_subject_id', 'description', 'season_environment',
               'assigned_from_geo', 'texture', 'taxon_id', 'depth',
               'host_taxid', 'common_name', 'water_content_soil', 'elevation',
               'temp', 'tot_nitro', 'samp_salinity', 'altitude', 'env_biome',
               'country', 'ph', 'anonymized_name', 'tot_org_carb',
               'description_duplicate', 'env_feature', 'latitude', 'longitude',
               'sample_id'}
        self.assertEqual(set(obs), exp)

    def test_study_id(self):
        """Ensure that the correct study ID is returned"""
        self.assertEqual(self.tester.study_id, 1)

    def test_init_unknown_error(self):
        """Init raises an error if the id is not known"""
        with self.assertRaises(QiitaDBUnknownIDError):
            SampleTemplate(2)

    def test_init(self):
        """Init successfully instantiates the object"""
        st = SampleTemplate(1)
        self.assertTrue(st.id, 1)

    def test_table_name(self):
        """Table name return the correct string"""
        obs = SampleTemplate._table_name(self.test_study.id)
        self.assertEqual(obs, "sample_1")

    def test_exists_true(self):
        """Exists returns true when the SampleTemplate already exists"""
        self.assertTrue(SampleTemplate.exists(self.test_study.id))

    def test_get_sample_ids(self):
        """get_sample_ids returns the correct set of sample ids"""
        conn_handler = SQLConnectionHandler()
        obs = self.tester._get_sample_ids(conn_handler)
        self.assertEqual(obs, self.exp_sample_ids)

    def test_len(self):
        """Len returns the correct number of sample ids"""
        self.assertEqual(len(self.tester), 27)

    def test_getitem(self):
        """Get item returns the correct sample object"""
        obs = self.tester['1.SKM7.640188']
        exp = Sample('1.SKM7.640188', self.tester)
        self.assertEqual(obs, exp)

    def test_getitem_error(self):
        """Get item raises an error if key does not exists"""
        with self.assertRaises(KeyError):
            self.tester['Not_a_Sample']

    def test_categories(self):
        exp = {'season_environment', 'assigned_from_geo',
               'texture', 'taxon_id', 'depth', 'host_taxid',
               'common_name', 'water_content_soil', 'elevation',
               'temp', 'tot_nitro', 'samp_salinity', 'altitude',
               'env_biome', 'country', 'ph', 'anonymized_name',
               'tot_org_carb', 'description_duplicate', 'env_feature',
               'physical_specimen_location',
               'physical_specimen_remaining', 'dna_extracted',
               'sample_type', 'collection_timestamp', 'host_subject_id',
               'description', 'latitude', 'longitude'}
        obs = set(self.tester.categories())
        self.assertItemsEqual(obs, exp)

    def test_iter(self):
        """iter returns an iterator over the sample ids"""
        obs = self.tester.__iter__()
        self.assertTrue(isinstance(obs, Iterable))
        self.assertEqual(set(obs), self.exp_sample_ids)

    def test_contains_true(self):
        """contains returns true if the sample id exists"""
        self.assertTrue('1.SKM7.640188' in self.tester)

    def test_contains_false(self):
        """contains returns false if the sample id does not exists"""
        self.assertFalse('Not_a_Sample' in self.tester)

    def test_keys(self):
        """keys returns an iterator over the sample ids"""
        obs = self.tester.keys()
        self.assertTrue(isinstance(obs, Iterable))
        self.assertEqual(set(obs), self.exp_sample_ids)

    def test_values(self):
        """values returns an iterator over the values"""
        obs = self.tester.values()
        self.assertTrue(isinstance(obs, Iterable))
        exp = {Sample('1.SKB1.640202', self.tester),
               Sample('1.SKB2.640194', self.tester),
               Sample('1.SKB3.640195', self.tester),
               Sample('1.SKB4.640189', self.tester),
               Sample('1.SKB5.640181', self.tester),
               Sample('1.SKB6.640176', self.tester),
               Sample('1.SKB7.640196', self.tester),
               Sample('1.SKB8.640193', self.tester),
               Sample('1.SKB9.640200', self.tester),
               Sample('1.SKD1.640179', self.tester),
               Sample('1.SKD2.640178', self.tester),
               Sample('1.SKD3.640198', self.tester),
               Sample('1.SKD4.640185', self.tester),
               Sample('1.SKD5.640186', self.tester),
               Sample('1.SKD6.640190', self.tester),
               Sample('1.SKD7.640191', self.tester),
               Sample('1.SKD8.640184', self.tester),
               Sample('1.SKD9.640182', self.tester),
               Sample('1.SKM1.640183', self.tester),
               Sample('1.SKM2.640199', self.tester),
               Sample('1.SKM3.640197', self.tester),
               Sample('1.SKM4.640180', self.tester),
               Sample('1.SKM5.640177', self.tester),
               Sample('1.SKM6.640187', self.tester),
               Sample('1.SKM7.640188', self.tester),
               Sample('1.SKM8.640201', self.tester),
               Sample('1.SKM9.640192', self.tester)}
        # Creating a list and looping over it since unittest does not call
        # the __eq__ function on the objects
        for o, e in zip(sorted(list(obs), key=lambda x: x.id),
                        sorted(exp, key=lambda x: x.id)):
            self.assertEqual(o, e)

    def test_items(self):
        """items returns an iterator over the (key, value) tuples"""
        obs = self.tester.items()
        self.assertTrue(isinstance(obs, Iterable))
        exp = [('1.SKB1.640202', Sample('1.SKB1.640202', self.tester)),
               ('1.SKB2.640194', Sample('1.SKB2.640194', self.tester)),
               ('1.SKB3.640195', Sample('1.SKB3.640195', self.tester)),
               ('1.SKB4.640189', Sample('1.SKB4.640189', self.tester)),
               ('1.SKB5.640181', Sample('1.SKB5.640181', self.tester)),
               ('1.SKB6.640176', Sample('1.SKB6.640176', self.tester)),
               ('1.SKB7.640196', Sample('1.SKB7.640196', self.tester)),
               ('1.SKB8.640193', Sample('1.SKB8.640193', self.tester)),
               ('1.SKB9.640200', Sample('1.SKB9.640200', self.tester)),
               ('1.SKD1.640179', Sample('1.SKD1.640179', self.tester)),
               ('1.SKD2.640178', Sample('1.SKD2.640178', self.tester)),
               ('1.SKD3.640198', Sample('1.SKD3.640198', self.tester)),
               ('1.SKD4.640185', Sample('1.SKD4.640185', self.tester)),
               ('1.SKD5.640186', Sample('1.SKD5.640186', self.tester)),
               ('1.SKD6.640190', Sample('1.SKD6.640190', self.tester)),
               ('1.SKD7.640191', Sample('1.SKD7.640191', self.tester)),
               ('1.SKD8.640184', Sample('1.SKD8.640184', self.tester)),
               ('1.SKD9.640182', Sample('1.SKD9.640182', self.tester)),
               ('1.SKM1.640183', Sample('1.SKM1.640183', self.tester)),
               ('1.SKM2.640199', Sample('1.SKM2.640199', self.tester)),
               ('1.SKM3.640197', Sample('1.SKM3.640197', self.tester)),
               ('1.SKM4.640180', Sample('1.SKM4.640180', self.tester)),
               ('1.SKM5.640177', Sample('1.SKM5.640177', self.tester)),
               ('1.SKM6.640187', Sample('1.SKM6.640187', self.tester)),
               ('1.SKM7.640188', Sample('1.SKM7.640188', self.tester)),
               ('1.SKM8.640201', Sample('1.SKM8.640201', self.tester)),
               ('1.SKM9.640192', Sample('1.SKM9.640192', self.tester))]
        # Creating a list and looping over it since unittest does not call
        # the __eq__ function on the objects
        for o, e in zip(sorted(list(obs)), sorted(exp)):
            self.assertEqual(o, e)

    def test_get(self):
        """get returns the correct sample object"""
        obs = self.tester.get('1.SKM7.640188')
        exp = Sample('1.SKM7.640188', self.tester)
        self.assertEqual(obs, exp)

    def test_get_none(self):
        """get returns none if the sample id is not present"""
        self.assertTrue(self.tester.get('Not_a_Sample') is None)

    def test_add_common_creation_steps_to_queue(self):
        """add_common_creation_steps_to_queue adds the correct sql statements
        """
        metadata_dict = {
            '2.Sample1': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 1',
                          'str_column': 'Value for sample 1',
                          'int_column': 1,
                          'latitude': 42.42,
                          'longitude': 41.41},
            '2.Sample2': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'int_column': 2,
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 2',
                          'str_column': 'Value for sample 2',
                          'latitude': 4.2,
                          'longitude': 1.1},
            '2.Sample3': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 3',
                          'str_column': 'Value for sample 3',
                          'int_column': 3,
                          'latitude': 4.8,
                          'longitude': 4.41},
            }
        metadata = pd.DataFrame.from_dict(metadata_dict, orient='index')

        conn_handler = SQLConnectionHandler()
        queue_name = "TEST_QUEUE"
        conn_handler.create_queue(queue_name)
        SampleTemplate._add_common_creation_steps_to_queue(
            metadata, 2, conn_handler, queue_name)

        sql_insert_required = (
            'INSERT INTO qiita.study_sample (study_id, sample_id) '
            'VALUES (%s, %s)')

        sql_insert_sample_cols = (
            'INSERT INTO qiita.study_sample_columns '
            '(study_id, column_name, column_type) '
            'VALUES (%s, %s, %s)')

        sql_crate_table = (
            'CREATE TABLE qiita.sample_2 (sample_id varchar NOT NULL, '
            'collection_timestamp timestamp, description varchar, '
            'dna_extracted bool, host_subject_id varchar, int_column integer, '
            'latitude float8, longitude float8, '
            'physical_specimen_location varchar, '
            'physical_specimen_remaining bool, sample_type varchar, '
            'str_column varchar, '
            'CONSTRAINT fk_sample_2 FOREIGN KEY (sample_id) REFERENCES '
            'qiita.study_sample (sample_id) ON UPDATE CASCADE)')

        sql_insert_dynamic = (
            'INSERT INTO qiita.sample_2 '
            '(sample_id, collection_timestamp, description, dna_extracted, '
            'host_subject_id, int_column, latitude, longitude, '
            'physical_specimen_location, physical_specimen_remaining, '
            'sample_type, str_column) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)')
        sql_insert_dynamic_params_1 = (
            '2.Sample1', datetime(2014, 5, 29, 12, 24, 51), 'Test Sample 1',
            True, 'NotIdentified', 1, 42.42, 41.41, 'location1', True, 'type1',
            'Value for sample 1')
        sql_insert_dynamic_params_2 = (
            '2.Sample2', datetime(2014, 5, 29, 12, 24, 51), 'Test Sample 2',
            True, 'NotIdentified', 2, 4.2, 1.1, 'location1', True, 'type1',
            'Value for sample 2')
        sql_insert_dynamic_params_3 = (
            '2.Sample3', datetime(2014, 5, 29, 12, 24, 51), 'Test Sample 3',
            True, 'NotIdentified', 3, 4.8, 4.41, 'location1', True, 'type1',
            'Value for sample 3')

        exp = [
            (sql_insert_required, (2, '2.Sample1')),
            (sql_insert_required, (2, '2.Sample2')),
            (sql_insert_required, (2, '2.Sample3')),
            (sql_insert_sample_cols, (2, 'collection_timestamp', 'timestamp')),
            (sql_insert_sample_cols, (2, 'description', 'varchar')),
            (sql_insert_sample_cols, (2, 'dna_extracted', 'bool')),
            (sql_insert_sample_cols, (2, 'host_subject_id', 'varchar')),
            (sql_insert_sample_cols, (2, 'int_column', 'integer')),
            (sql_insert_sample_cols, (2, 'latitude', 'float8')),
            (sql_insert_sample_cols, (2, 'longitude', 'float8')),
            (sql_insert_sample_cols,
                (2, 'physical_specimen_location', 'varchar')),
            (sql_insert_sample_cols,
                (2, 'physical_specimen_remaining', 'bool')),
            (sql_insert_sample_cols, (2, 'sample_type', 'varchar')),
            (sql_insert_sample_cols, (2, 'str_column', 'varchar')),
            (sql_crate_table, None),
            (sql_insert_dynamic, sql_insert_dynamic_params_1),
            (sql_insert_dynamic, sql_insert_dynamic_params_2),
            (sql_insert_dynamic, sql_insert_dynamic_params_3)]
        self.assertEqual(conn_handler.queues[queue_name], exp)

    def test_clean_validate_template_error_bad_chars(self):
        """Raises an error if there are invalid characters in the sample names
        """
        self.metadata.index = ['o()xxxx[{::::::::>', 'sample.1', 'sample.3']
        with self.assertRaises(QiitaDBColumnError):
            SampleTemplate._clean_validate_template(self.metadata, 2,
                                                    SAMPLE_TEMPLATE_COLUMNS)

    def test_clean_validate_template_error_duplicate_cols(self):
        """Raises an error if there are duplicated columns in the template"""
        self.metadata['STR_COLUMN'] = pd.Series(['foo', 'bar', 'foobar'],
                                                index=self.metadata.index)

        with self.assertRaises(QiitaDBDuplicateHeaderError):
            SampleTemplate._clean_validate_template(self.metadata, 2,
                                                    SAMPLE_TEMPLATE_COLUMNS)

    def test_clean_validate_template_warning_missing(self):
        """Warns if the template is missing a required column"""
        metadata_dict = {
            'Sample1': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 1',
                        'latitude': 42.42,
                        'longitude': 41.41}
            }
        metadata = pd.DataFrame.from_dict(metadata_dict, orient='index')
        obs = npt.assert_warns(QiitaDBWarning,
                               SampleTemplate._clean_validate_template,
                               metadata, 2, SAMPLE_TEMPLATE_COLUMNS)
        metadata_dict = {
            '2.Sample1': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 1',
                          'latitude': 42.42,
                          'longitude': 41.41}
            }
        exp = pd.DataFrame.from_dict(metadata_dict, orient='index')
        obs.sort_index(axis=0, inplace=True)
        obs.sort_index(axis=1, inplace=True)
        exp.sort_index(axis=0, inplace=True)
        exp.sort_index(axis=1, inplace=True)
        assert_frame_equal(obs, exp)

    def test_clean_validate_template(self):
        obs = SampleTemplate._clean_validate_template(self.metadata, 2,
                                                      SAMPLE_TEMPLATE_COLUMNS)
        metadata_dict = {
            '2.Sample1': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 1',
                          'str_column': 'Value for sample 1',
                          'int_column': 1,
                          'latitude': 42.42,
                          'longitude': 41.41,
                          'taxon_id': 9606,
                          'scientific_name': 'homo sapiens'},
            '2.Sample2': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'int_column': 2,
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 2',
                          'str_column': 'Value for sample 2',
                          'latitude': 4.2,
                          'longitude': 1.1,
                          'taxon_id': 9606,
                          'scientific_name': 'homo sapiens'},
            '2.Sample3': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 3',
                          'str_column': 'Value for sample 3',
                          'int_column': 3,
                          'latitude': 4.8,
                          'longitude': 4.41,
                          'taxon_id': 9606,
                          'scientific_name': 'homo sapiens'},
            }
        exp = pd.DataFrame.from_dict(metadata_dict, orient='index')
        obs.sort_index(axis=0, inplace=True)
        obs.sort_index(axis=1, inplace=True)
        exp.sort_index(axis=0, inplace=True)
        exp.sort_index(axis=1, inplace=True)
        assert_frame_equal(obs, exp)


@qiita_test_checker()
class TestSampleTemplateReadWrite(BaseTestSampleTemplate):
    """Tests the SampleTemplate class"""

    def setUp(self):
        self._set_up()
        info = {
            "timeseries_type_id": 1,
            "metadata_complete": True,
            "mixs_compliant": True,
            "number_samples_collected": 25,
            "number_samples_promised": 28,
            "portal_type_id": 3,
            "study_alias": "FCM",
            "study_description": "Microbiome of people who eat nothing but "
                                 "fried chicken",
            "study_abstract": "Exploring how a high fat diet changes the "
                              "gut microbiome",
            "emp_person_id": StudyPerson(2),
            "principal_investigator_id": StudyPerson(3),
            "lab_person_id": StudyPerson(1)
        }
        self.new_study = Study.create(User('test@foo.bar'),
                                      "Fried Chicken Microbiome", [1], info)

    def test_create_duplicate(self):
        """Create raises an error when creating a duplicated SampleTemplate"""
        with self.assertRaises(QiitaDBDuplicateError):
            SampleTemplate.create(self.metadata, self.test_study)

    def test_create_duplicate_header(self):
        """Create raises an error when duplicate headers are present"""
        self.metadata['STR_COLUMN'] = pd.Series(['', '', ''],
                                                index=self.metadata.index)
        with self.assertRaises(QiitaDBDuplicateHeaderError):
            SampleTemplate.create(self.metadata, self.new_study)

    def test_create_bad_sample_names(self):
        """Create raises an error when duplicate headers are present"""
        # set a horrible list of sample names
        self.metadata.index = ['o()xxxx[{::::::::>', 'sample.1', 'sample.3']
        with self.assertRaises(QiitaDBColumnError):
            SampleTemplate.create(self.metadata, self.new_study)

    def test_create_error_cleanup(self):
        """Create does not modify the database if an error happens"""
        metadata_dict = {
            'Sample1': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 1',
                        'group': 'Forcing the creation to fail',
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'}
            }
        metadata = pd.DataFrame.from_dict(metadata_dict, orient='index')
        with self.assertRaises(ValueError):
            SampleTemplate.create(metadata, self.new_study)

        sql = """SELECT EXISTS(
                    SELECT * FROM qiita.study_sample
                    WHERE sample_id=%s)"""
        sample_id = "%d.Sample1" % self.new_study.id
        self.assertFalse(
            self.conn_handler.execute_fetchone(sql, (sample_id,))[0])

        sql = """SELECT EXISTS(
                    SELECT * FROM qiita.study_sample_columns
                    WHERE study_id=%s)"""
        self.assertFalse(
            self.conn_handler.execute_fetchone(sql, (self.new_study.id,))[0])

        self.assertFalse(
            exists_table("sample_%d" % self.new_study.id, self.conn_handler))

    def test_create(self):
        """Creates a new SampleTemplate"""
        st = SampleTemplate.create(self.metadata, self.new_study)
        new_id = self.new_study.id
        # The returned object has the correct id
        self.assertEqual(st.id, new_id)

        # The table qiita.study_sample has been correctly populates
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.study_sample WHERE study_id=%s", (new_id,))
        exp = [["%s.Sample1" % new_id, new_id],
               ["%s.Sample2" % new_id, new_id],
               ["%s.Sample3" % new_id, new_id]]
        self.assertEqual(obs, exp)

        # The relevant rows have been added to the study_sample_columns
        sql = """SELECT study_id, column_name, column_type
                 FROM qiita.study_sample_columns
                 WHERE study_id=%s
                 ORDER BY column_name"""
        obs = self.conn_handler.execute_fetchall(sql, (new_id,))

        # study_id, column_name, column_type
        exp = [[new_id, 'collection_timestamp', 'timestamp'],
               [new_id, 'description', 'varchar'],
               [new_id, 'dna_extracted', 'bool'],
               [new_id, 'host_subject_id', 'varchar'],
               [new_id, 'int_column', 'integer'],
               [new_id, 'latitude', 'float8'],
               [new_id, 'longitude', 'float8'],
               [new_id, 'physical_specimen_location', 'varchar'],
               [new_id, 'physical_specimen_remaining', 'bool'],
               [new_id, 'sample_type', 'varchar'],
               [new_id, 'scientific_name', 'varchar'],
               [new_id, 'str_column', 'varchar'],
               [new_id, 'taxon_id', 'integer']]
        self.assertEqual(obs, exp)

        # The new table exists
        self.assertTrue(exists_table("sample_%s" % new_id, self.conn_handler))

        # The new table hosts the correct values
        sql = "SELECT * FROM qiita.sample_{0}".format(new_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]

        exp = [{'sample_id': "%s.Sample1" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 1",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 1,
                'latitude': 42.42,
                'longitude': 41.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 1",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.Sample2" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 2",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 2,
                'latitude': 4.2,
                'longitude': 1.1,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 2",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.Sample3" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 3",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 3,
                'latitude': 4.8,
                'longitude': 4.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 3",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertEqual(obs, exp)

    def test_create_int_prefix(self):
        """Creates a new SampleTemplate with sample names int prefixed"""
        new_id = self.new_study.id
        st = SampleTemplate.create(self.metadata_int_pref, self.new_study)
        # The returned object has the correct id
        self.assertEqual(st.id, new_id)

        # The relevant rows to study_sample have been added.
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.study_sample WHERE study_id=%s", (new_id,))
        exp = [["%s.12.Sample1" % new_id, new_id],
               ["%s.12.Sample2" % new_id, new_id],
               ["%s.12.Sample3" % new_id, new_id]]
        self.assertEqual(obs, exp)

        # The relevant rows have been added to the study_sample_columns
        sql = """SELECT study_id, column_name, column_type
                 FROM qiita.study_sample_columns
                 WHERE study_id=%s
                 ORDER BY column_name"""
        obs = self.conn_handler.execute_fetchall(sql, (new_id,))

        # study_id, column_name, column_type
        exp = [[new_id, 'collection_timestamp', 'timestamp'],
               [new_id, 'description', 'varchar'],
               [new_id, 'dna_extracted', 'bool'],
               [new_id, 'host_subject_id', 'varchar'],
               [new_id, 'int_column', 'integer'],
               [new_id, 'latitude', 'float8'],
               [new_id, 'longitude', 'float8'],
               [new_id, 'physical_specimen_location', 'varchar'],
               [new_id, 'physical_specimen_remaining', 'bool'],
               [new_id, 'sample_type', 'varchar'],
               [new_id, 'scientific_name', 'varchar'],
               [new_id, 'str_column', 'varchar'],
               [new_id, 'taxon_id', 'integer']]
        self.assertEqual(obs, exp)

        # The new table exists
        self.assertTrue(exists_table("sample_%s" % new_id, self.conn_handler))

        # The new table hosts the correct values
        sql = "SELECT * FROM qiita.sample_{0}".format(new_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]

        exp = [{'sample_id': "%s.12.Sample1" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 1",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 1,
                'latitude': 42.42,
                'longitude': 41.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 1",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.12.Sample2" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 2",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 2,
                'latitude': 4.2,
                'longitude': 1.1,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 2",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.12.Sample3" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 3",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 3,
                'latitude': 4.8,
                'longitude': 4.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 3",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertEqual(obs, exp)

    def test_create_str_prefixes(self):
        """Creates a new SampleTemplate with sample names string prefixed"""
        new_id = self.new_study.id
        st = SampleTemplate.create(self.metadata_str_prefix, self.new_study)
        # The returned object has the correct id
        self.assertEqual(st.id, new_id)

        # The table qiita.study_sample has been correctly populates
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.study_sample WHERE study_id=%s", (new_id,))
        exp = [["%s.foo.Sample1" % new_id, new_id],
               ["%s.bar.Sample2" % new_id, new_id],
               ["%s.foo.Sample3" % new_id, new_id]]
        self.assertItemsEqual(obs, exp)

        # The relevant rows have been added to the study_sample_columns
        sql = """SELECT study_id, column_name, column_type
                 FROM qiita.study_sample_columns
                 WHERE study_id=%s
                 ORDER BY column_name"""
        obs = self.conn_handler.execute_fetchall(sql, (new_id,))

        # study_id, column_name, column_type
        exp = [[new_id, 'collection_timestamp', 'timestamp'],
               [new_id, 'description', 'varchar'],
               [new_id, 'dna_extracted', 'bool'],
               [new_id, 'host_subject_id', 'varchar'],
               [new_id, 'int_column', 'integer'],
               [new_id, 'latitude', 'float8'],
               [new_id, 'longitude', 'float8'],
               [new_id, 'physical_specimen_location', 'varchar'],
               [new_id, 'physical_specimen_remaining', 'bool'],
               [new_id, 'sample_type', 'varchar'],
               [new_id, 'scientific_name', 'varchar'],
               [new_id, 'str_column', 'varchar'],
               [new_id, 'taxon_id', 'integer']]
        self.assertEqual(obs, exp)

        # The new table exists
        self.assertTrue(exists_table("sample_%s" % new_id, self.conn_handler))

        # The new table hosts the correct values
        sql = "SELECT * FROM qiita.sample_{0}".format(new_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]

        exp = [{'sample_id': "%s.foo.Sample1" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 1",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 1,
                'latitude': 42.42,
                'longitude': 41.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 1",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.bar.Sample2" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 2",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 2,
                'latitude': 4.2,
                'longitude': 1.1,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 2",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.foo.Sample3" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 3",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 3,
                'latitude': 4.8,
                'longitude': 4.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 3",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertItemsEqual(obs, exp)

    def test_create_already_prefixed_samples(self):
        """Creates a new SampleTemplate with the samples already prefixed"""
        st = npt.assert_warns(QiitaDBWarning, SampleTemplate.create,
                              self.metadata_prefixed, self.new_study)
        new_id = self.new_study.id
        # The returned object has the correct id
        self.assertEqual(st.id, new_id)

        # The table qiita.study_sample has been correctly populates
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.study_sample WHERE study_id=%s", (new_id,))
        exp = [["%s.Sample1" % new_id, new_id],
               ["%s.Sample2" % new_id, new_id],
               ["%s.Sample3" % new_id, new_id]]
        self.assertEqual(obs, exp)

        # The relevant rows have been added to the study_sample_columns
        sql = """SELECT study_id, column_name, column_type
                 FROM qiita.study_sample_columns
                 WHERE study_id=%s
                 ORDER BY column_name"""
        obs = self.conn_handler.execute_fetchall(sql, (new_id,))

        # study_id, column_name, column_type
        exp = [[new_id, 'collection_timestamp', 'timestamp'],
               [new_id, 'description', 'varchar'],
               [new_id, 'dna_extracted', 'bool'],
               [new_id, 'host_subject_id', 'varchar'],
               [new_id, 'int_column', 'integer'],
               [new_id, 'latitude', 'float8'],
               [new_id, 'longitude', 'float8'],
               [new_id, 'physical_specimen_location', 'varchar'],
               [new_id, 'physical_specimen_remaining', 'bool'],
               [new_id, 'sample_type', 'varchar'],
               [new_id, 'scientific_name', 'varchar'],
               [new_id, 'str_column', 'varchar'],
               [new_id, 'taxon_id', 'integer']]
        self.assertEqual(obs, exp)

        # The new table exists
        self.assertTrue(exists_table("sample_%s" % new_id, self.conn_handler))

        # The new table hosts the correct values
        sql = "SELECT * FROM qiita.sample_{0}".format(new_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]

        exp = [{'sample_id': "%s.Sample1" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 1",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 1,
                'latitude': 42.42,
                'longitude': 41.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 1",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.Sample2" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 2",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 2,
                'latitude': 4.2,
                'longitude': 1.1,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 2",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': "%s.Sample3" % new_id,
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'description': "Test Sample 3",
                'dna_extracted': True,
                'host_subject_id': "NotIdentified",
                'int_column': 3,
                'latitude': 4.8,
                'longitude': 4.41,
                'physical_specimen_location': "location1",
                'physical_specimen_remaining': True,
                'sample_type': "type1",
                'str_column': "Value for sample 3",
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertEqual(obs, exp)

    def test_delete(self):
        """Deletes Sample template 1"""
        st = SampleTemplate.create(self.metadata, self.new_study)
        st_id = st.id
        SampleTemplate.delete(st.id)

        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.study_sample WHERE study_id=%s" % st_id)
        exp = []
        self.assertEqual(obs, exp)

        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.study_sample_columns WHERE study_id=%s"
            % st_id)
        exp = []
        self.assertEqual(obs, exp)

        with self.assertRaises(ValueError):
            self.conn_handler.execute_fetchall(
                "SELECT * FROM qiita.sample_%s" % st_id)

        with self.assertRaises(QiitaDBError):
            SampleTemplate.delete(1)

    def test_delete_unkonwn_id_error(self):
        """Try to delete a non existent prep template"""
        with self.assertRaises(QiitaDBUnknownIDError):
            SampleTemplate.delete(5)

    def test_exists_false(self):
        """Exists returns false when the SampleTemplate does not exists"""
        self.assertFalse(SampleTemplate.exists(self.new_study.id))

    def test_update_category(self):
        with self.assertRaises(QiitaDBUnknownIDError):
            self.tester.update_category('country', {"foo": "bar"})

        with self.assertRaises(QiitaDBColumnError):
            self.tester.update_category('missing column',
                                        {'1.SKM7.640188': 'stuff'})

        negtest = self.tester['1.SKM7.640188']['country']

        mapping = {'1.SKB1.640202': "1",
                   '1.SKB5.640181': "2",
                   '1.SKD6.640190': "3"}

        self.tester.update_category('country', mapping)

        self.assertEqual(self.tester['1.SKB1.640202']['country'], "1")
        self.assertEqual(self.tester['1.SKB5.640181']['country'], "2")
        self.assertEqual(self.tester['1.SKD6.640190']['country'], "3")
        self.assertEqual(self.tester['1.SKM7.640188']['country'], negtest)

        # testing that if fails when trying to change an int column value
        # to str
        st = SampleTemplate.create(self.metadata, self.new_study)

        sql = """SELECT * FROM qiita.sample_2 ORDER BY sample_id"""
        before = self.conn_handler.execute_fetchall(sql)
        mapping = {'2.Sample1': 1, '2.Sample2': "no_value"}

        with self.assertRaises(ValueError):
            st.update_category('int_column', mapping)

        after = self.conn_handler.execute_fetchall(sql)

        self.assertEqual(before, after)

    def test_update(self):
        """Updates values in existing mapping file"""
        # creating a new sample template
        st = SampleTemplate.create(self.metadata, self.new_study)
        # updating the sample template
        st.update(self.metadata_dict_updated)

        # validating values
        exp = self.metadata_dict_updated_dict['Sample1'].values()
        obs = st.get('2.Sample1').values()
        self.assertItemsEqual(obs, exp)

        exp = self.metadata_dict_updated_dict['Sample2'].values()
        obs = st.get('2.Sample2').values()
        self.assertItemsEqual(obs, exp)

        exp = self.metadata_dict_updated_dict['Sample3'].values()
        obs = st.get('2.Sample3').values()
        self.assertItemsEqual(obs, exp)

        # checking errors
        with self.assertRaises(QiitaDBError):
            st.update(self.metadata_dict_updated_sample_error)
        with self.assertRaises(QiitaDBError):
            st.update(self.metadata_dict_updated_column_error)

    def test_generate_files(self):
        fp_count = get_count("qiita.filepath")
        self.tester.generate_files()
        obs = get_count("qiita.filepath")
        # We just make sure that the count has been increased by 2, since
        # the contents of the files have been tested elsewhere.
        self.assertEqual(obs, fp_count + 3)

    def test_to_file(self):
        """to file writes a tab delimited file with all the metadata"""
        fd, fp = mkstemp()
        close(fd)
        st = SampleTemplate.create(self.metadata, self.new_study)
        st.to_file(fp)
        self._clean_up_files.append(fp)
        with open(fp, 'U') as f:
            obs = f.read()
        self.assertEqual(obs, EXP_SAMPLE_TEMPLATE)

        fd, fp = mkstemp()
        close(fd)
        st.to_file(fp, {'2.Sample1', '2.Sample3'})
        self._clean_up_files.append(fp)

        with open(fp, 'U') as f:
            obs = f.read()
        self.assertEqual(obs, EXP_SAMPLE_TEMPLATE_FEWER_SAMPLES)

    def test_get_filepath(self):
        # we will check that there is a new id only because the path will
        # change based on time and the same functionality is being tested
        # in data.py
        exp_id = self.conn_handler.execute_fetchone(
            "SELECT count(1) FROM qiita.filepath")[0] + 1
        st = SampleTemplate.create(self.metadata, self.new_study)
        self.assertEqual(st.get_filepaths()[0][0], exp_id)

        # testing current functionaly, to add a new sample template
        # you need to erase it first
        SampleTemplate.delete(st.id)
        exp_id += 1
        st = SampleTemplate.create(self.metadata, self.new_study)
        self.assertEqual(st.get_filepaths()[0][0], exp_id)

    def test_extend_error(self):
        """extend raises an error if no new columns/samples are added"""
        st = SampleTemplate.create(self.metadata, self.new_study)
        with self.assertRaises(QiitaDBError):
            st.extend(self.metadata)

    def test_extend_add_samples(self):
        """extend correctly works adding new samples"""
        st = SampleTemplate.create(self.metadata, self.new_study)

        md_dict = {
            'Sample4': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 4',
                        'str_column': 'Value for sample 4',
                        'int_column': 4,
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'},
            'Sample5': {'physical_specimen_location': 'location1',
                        'physical_specimen_remaining': True,
                        'dna_extracted': True,
                        'sample_type': 'type1',
                        'collection_timestamp':
                        datetime(2014, 5, 29, 12, 24, 51),
                        'host_subject_id': 'NotIdentified',
                        'Description': 'Test Sample 5',
                        'str_column': 'Value for sample 5',
                        'int_column': 5,
                        'latitude': 42.42,
                        'longitude': 41.41,
                        'taxon_id': 9606,
                        'scientific_name': 'homo sapiens'}}
        md_ext = pd.DataFrame.from_dict(md_dict, orient='index')

        st.extend(md_ext)

        # Test samples were appended successfully to the required sample info
        # table
        study_id = self.new_study.id
        sql = """SELECT *
                 FROM qiita.study_sample
                 WHERE study_id=%s"""
        obs = [dict(o)
               for o in self.conn_handler.execute_fetchall(sql, (study_id,))]
        exp = [{'sample_id': '2.Sample1',
                'study_id': 2},
               {'sample_id': '2.Sample2',
                'study_id': 2},
               {'sample_id': '2.Sample3',
                'study_id': 2},
               {'sample_id': '2.Sample4',
                'study_id': 2},
               {'sample_id': '2.Sample5',
                'study_id': 2}]
        self.assertItemsEqual(obs, exp)

        # Test samples were appended successfully to the dynamic table
        sql = "SELECT * FROM qiita.sample_{0}".format(study_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]
        exp = [{'sample_id': '2.Sample1',
                'int_column': 1,
                'str_column': 'Value for sample 1',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 1',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '2.Sample2',
                'int_column': 2,
                'str_column': 'Value for sample 2',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 2',
                'latitude': 4.2,
                'longitude': 1.1,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '2.Sample3',
                'int_column': 3,
                'str_column': 'Value for sample 3',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 3',
                'latitude': 4.8,
                'longitude': 4.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '2.Sample4',
                'int_column': 4,
                'str_column': 'Value for sample 4',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 4',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '2.Sample5',
                'int_column': 5,
                'str_column': 'Value for sample 5',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 5',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertItemsEqual(obs, exp)

    def test_extend_add_duplicate_samples(self):
        """extend correctly works adding new samples and warns for duplicates
        """
        st = SampleTemplate.create(self.metadata, self.new_study)

        self.metadata_dict['Sample4'] = {
            'physical_specimen_location': 'location1',
            'physical_specimen_remaining': True,
            'dna_extracted': True,
            'sample_type': 'type1',
            'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
            'host_subject_id': 'NotIdentified',
            'Description': 'Test Sample 4',
            'str_column': 'Value for sample 4',
            'int_column': 4,
            'latitude': 42.42,
            'longitude': 41.41,
            'taxon_id': 9606,
            'scientific_name': 'homo sapiens'}

        # Change a couple of values on the existent samples to test that
        # they remain unchanged
        self.metadata_dict['Sample1']['Description'] = 'Changed'
        self.metadata_dict['Sample2']['str_column'] = 'Changed dynamic'

        md_ext = pd.DataFrame.from_dict(self.metadata_dict, orient='index')
        # Make sure adding duplicate samples raises warning
        npt.assert_warns(QiitaDBWarning, st.extend, md_ext)

        # Make sure the new sample has been added and the values for the
        # existent samples did not change
        study_id = self.new_study.id
        sql = """SELECT *
                 FROM qiita.study_sample
                 WHERE study_id=%s"""
        obs = [dict(o)
               for o in self.conn_handler.execute_fetchall(sql, (study_id,))]
        exp = [{'sample_id': '%s.Sample1' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample2' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample3' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample4' % study_id,
                'study_id': 2}]
        self.assertItemsEqual(obs, exp)

        # Test samples were appended successfully to the dynamic table
        sql = "SELECT * FROM qiita.sample_{0}".format(study_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]
        exp = [{'sample_id': '%s.Sample1' % study_id,
                'int_column': 1,
                'str_column': 'Value for sample 1',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 1',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample2' % study_id,
                'int_column': 2,
                'str_column': 'Value for sample 2',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 2',
                'latitude': 4.2,
                'longitude': 1.1,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample3' % study_id,
                'int_column': 3,
                'str_column': 'Value for sample 3',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 3',
                'latitude': 4.8,
                'longitude': 4.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample4' % study_id,
                'int_column': 4,
                'str_column': 'Value for sample 4',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 4',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertItemsEqual(obs, exp)

    def test_extend_new_columns(self):
        """extend correctly adds a new column"""
        st = SampleTemplate.create(self.metadata, self.new_study)

        self.metadata['NEWCOL'] = pd.Series(['val1', 'val2', 'val3'],
                                            index=self.metadata.index)
        self.metadata['NEW_COL'] = pd.Series(['val_1', 'val_2', 'val_3'],
                                             index=self.metadata.index)

        # Change some values to make sure that they do not change on extend
        self.metadata_dict['Sample1']['Description'] = 'Changed'
        self.metadata_dict['Sample2']['str_column'] = 'Changed dynamic'

        # Make sure it raises a warning indicating that the new columns will
        # be added for the existing samples
        npt.assert_warns(QiitaDBWarning, st.extend, self.metadata)

        study_id = self.new_study.id
        sql = "SELECT * FROM qiita.sample_{0}".format(study_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]
        exp = [{'sample_id': '%s.Sample1' % study_id,
                'int_column': 1,
                'str_column': 'Value for sample 1',
                'newcol': 'val1',
                'new_col': 'val_1',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 1',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample2' % study_id,
                'int_column': 2,
                'str_column': 'Value for sample 2',
                'newcol': 'val2',
                'new_col': 'val_2',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 2',
                'latitude': 4.2,
                'longitude': 1.1,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample3' % study_id,
                'int_column': 3,
                'str_column': 'Value for sample 3',
                'newcol': 'val3',
                'new_col': 'val_3',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 3',
                'latitude': 4.8,
                'longitude': 4.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertItemsEqual(obs, exp)

        sql = """SELECT *
                 FROM qiita.study_sample
                 WHERE study_id=%s"""
        obs = [dict(o)
               for o in self.conn_handler.execute_fetchall(sql, (study_id,))]
        exp = [{'sample_id': '%s.Sample1' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample2' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample3' % study_id,
                'study_id': 2}]
        self.assertItemsEqual(obs, exp)

    def test_extend_new_samples_and_columns(self):
        """extend correctly adds new samples and columns at the same time"""
        st = SampleTemplate.create(self.metadata, self.new_study)

        self.metadata_dict['Sample4'] = {
            'physical_specimen_location': 'location1',
            'physical_specimen_remaining': True,
            'dna_extracted': True,
            'sample_type': 'type1',
            'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
            'host_subject_id': 'NotIdentified',
            'Description': 'Test Sample 4',
            'str_column': 'Value for sample 4',
            'int_column': 4,
            'latitude': 42.42,
            'longitude': 41.41,
            'taxon_id': 9606,
            'scientific_name': 'homo sapiens'}

        # Change a couple of values on the existent samples to test that
        # they remain unchanged
        self.metadata_dict['Sample1']['Description'] = 'Changed'
        self.metadata_dict['Sample2']['str_column'] = 'Changed dynamic'

        md_ext = pd.DataFrame.from_dict(self.metadata_dict, orient='index')

        md_ext['NEWCOL'] = pd.Series(['val1', 'val2', 'val3', 'val4'],
                                     index=md_ext.index)
        # Make sure adding duplicate samples raises warning
        npt.assert_warns(QiitaDBWarning, st.extend, md_ext)

        # Make sure the new sample and column have been added and the values
        # for the existent samples did not change
        study_id = self.new_study.id
        sql = """SELECT *
                 FROM qiita.study_sample
                 WHERE study_id=%s"""
        obs = [dict(o)
               for o in self.conn_handler.execute_fetchall(sql, (study_id,))]
        exp = [{'sample_id': '%s.Sample1' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample2' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample3' % study_id,
                'study_id': 2},
               {'sample_id': '%s.Sample4' % study_id,
                'study_id': 2}]
        self.assertItemsEqual(obs, exp)

        sql = "SELECT * FROM qiita.sample_{0}".format(study_id)
        obs = [dict(o) for o in self.conn_handler.execute_fetchall(sql)]
        exp = [{'sample_id': '%s.Sample1' % study_id,
                'int_column': 1,
                'str_column': 'Value for sample 1',
                'newcol': 'val1',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 1',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample2' % study_id,
                'int_column': 2,
                'str_column': 'Value for sample 2',
                'newcol': 'val2',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 2',
                'latitude': 4.2,
                'longitude': 1.1,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample3' % study_id,
                'int_column': 3,
                'str_column': 'Value for sample 3',
                'newcol': 'val3',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 3',
                'latitude': 4.8,
                'longitude': 4.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'},
               {'sample_id': '%s.Sample4' % study_id,
                'int_column': 4,
                'str_column': 'Value for sample 4',
                'newcol': 'val4',
                'physical_specimen_location': 'location1',
                'physical_specimen_remaining': True,
                'dna_extracted': True,
                'sample_type': 'type1',
                'collection_timestamp': datetime(2014, 5, 29, 12, 24, 51),
                'host_subject_id': 'NotIdentified',
                'description': 'Test Sample 4',
                'latitude': 42.42,
                'longitude': 41.41,
                'taxon_id': 9606,
                'scientific_name': 'homo sapiens'}]
        self.assertItemsEqual(obs, exp)

    def test_to_dataframe(self):
        st = SampleTemplate.create(self.metadata, self.new_study)
        obs = st.to_dataframe()

        exp_dict = {
            '2.Sample1': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 1',
                          'str_column': 'Value for sample 1',
                          'int_column': 1,
                          'latitude': 42.42,
                          'longitude': 41.41,
                          'taxon_id': 9606,
                          'scientific_name': 'homo sapiens'},
            '2.Sample2': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'int_column': 2,
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 2',
                          'str_column': 'Value for sample 2',
                          'latitude': 4.2,
                          'longitude': 1.1,
                          'taxon_id': 9606,
                          'scientific_name': 'homo sapiens'},
            '2.Sample3': {'physical_specimen_location': 'location1',
                          'physical_specimen_remaining': True,
                          'dna_extracted': True,
                          'sample_type': 'type1',
                          'collection_timestamp':
                          datetime(2014, 5, 29, 12, 24, 51),
                          'host_subject_id': 'NotIdentified',
                          'description': 'Test Sample 3',
                          'str_column': 'Value for sample 3',
                          'int_column': 3,
                          'latitude': 4.8,
                          'longitude': 4.41,
                          'taxon_id': 9606,
                          'scientific_name': 'homo sapiens'},
            }
        exp = pd.DataFrame.from_dict(exp_dict, orient='index')
        exp.index.name = 'sample_id'
        obs.sort_index(axis=0, inplace=True)
        obs.sort_index(axis=1, inplace=True)
        exp.sort_index(axis=0, inplace=True)
        exp.sort_index(axis=1, inplace=True)
        assert_frame_equal(obs, exp)

        obs = self.tester.to_dataframe()
        # We don't test the specific values as this would blow up the size
        # of this file as the amount of lines would go to ~1000

        # 27 samples
        self.assertEqual(len(obs), 27)
        exp = {'1.SKB1.640202', '1.SKB2.640194', '1.SKB3.640195',
               '1.SKB4.640189', '1.SKB5.640181', '1.SKB6.640176',
               '1.SKB7.640196', '1.SKB8.640193', '1.SKB9.640200',
               '1.SKD1.640179', '1.SKD2.640178', '1.SKD3.640198',
               '1.SKD4.640185', '1.SKD5.640186', '1.SKD6.640190',
               '1.SKD7.640191', '1.SKD8.640184', '1.SKD9.640182',
               '1.SKM1.640183', '1.SKM2.640199', '1.SKM3.640197',
               '1.SKM4.640180', '1.SKM5.640177', '1.SKM6.640187',
               '1.SKM7.640188', '1.SKM8.640201', '1.SKM9.640192'}
        self.assertEqual(set(obs.index), exp)

        self.assertEqual(set(obs.columns), {
            'physical_specimen_location', 'physical_specimen_remaining',
            'dna_extracted', 'sample_type', 'collection_timestamp',
            'host_subject_id', 'description', 'latitude', 'longitude',
            'season_environment', 'assigned_from_geo', 'texture',
            'taxon_id', 'depth', 'host_taxid', 'common_name',
            'water_content_soil', 'elevation', 'temp', 'tot_nitro',
            'samp_salinity', 'altitude', 'env_biome', 'country', 'ph',
            'anonymized_name', 'tot_org_carb', 'description_duplicate',
            'env_feature'})

    def test_check_restrictions(self):
        obs = self.tester.check_restrictions([SAMPLE_TEMPLATE_COLUMNS['EBI']])
        self.assertEqual(obs, {'scientific_name'})

        del self.metadata['collection_timestamp']
        st = npt.assert_warns(QiitaDBWarning, SampleTemplate.create,
                              self.metadata, self.new_study)
        obs = st.check_restrictions([SAMPLE_TEMPLATE_COLUMNS['EBI']])
        self.assertEqual(obs, {'collection_timestamp'})

EXP_SAMPLE_TEMPLATE = (
    "sample_name\tcollection_timestamp\tdescription\tdna_extracted\t"
    "host_subject_id\tint_column\tlatitude\tlongitude\t"
    "physical_specimen_location\tphysical_specimen_remaining\tsample_type\t"
    "scientific_name\tstr_column\ttaxon_id\n"
    "2.Sample1\t2014-05-29 12:24:51\tTest Sample 1\tTrue\tNotIdentified\t1\t"
    "42.42\t41.41\tlocation1\tTrue\ttype1\thomo sapiens\tValue for sample 1\t"
    "9606\n"
    "2.Sample2\t2014-05-29 12:24:51\tTest Sample 2\tTrue\tNotIdentified\t2\t"
    "4.2\t1.1\tlocation1\tTrue\ttype1\thomo sapiens\tValue for sample 2\t"
    "9606\n"
    "2.Sample3\t2014-05-29 12:24:51\tTest Sample 3\tTrue\tNotIdentified\t3\t"
    "4.8\t4.41\tlocation1\tTrue\ttype1\thomo sapiens\tValue for sample 3\t"
    "9606\n")

EXP_SAMPLE_TEMPLATE_FEWER_SAMPLES = (
    "sample_name\tcollection_timestamp\tdescription\tdna_extracted\t"
    "host_subject_id\tint_column\tlatitude\tlongitude\t"
    "physical_specimen_location\tphysical_specimen_remaining\tsample_type\t"
    "scientific_name\tstr_column\ttaxon_id\n"
    "2.Sample1\t2014-05-29 12:24:51\tTest Sample 1\tTrue\tNotIdentified\t1\t"
    "42.42\t41.41\tlocation1\tTrue\ttype1\thomo sapiens\tValue for sample 1\t"
    "9606\n"
    "2.Sample3\t2014-05-29 12:24:51\tTest Sample 3\tTrue\tNotIdentified\t3\t"
    "4.8\t4.41\tlocation1\tTrue\ttype1\thomo sapiens\tValue for sample 3\t"
    "9606\n")


if __name__ == '__main__':
    main()
