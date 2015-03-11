from unittest import TestCase, main
from os import remove
from os.path import exists, join
from datetime import datetime
from shutil import move

from biom import load_table
import pandas as pd

from qiita_core.util import qiita_test_checker
from qiita_db.analysis import Analysis, Collection
from qiita_db.job import Job
from qiita_db.user import User
from qiita_db.exceptions import QiitaDBStatusError
from qiita_db.util import get_mountpoint
from qiita_db.study import Study, StudyPerson
from qiita_db.data import ProcessedData
from qiita_db.metadata_template import SampleTemplate
# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------


@qiita_test_checker()
class TestAnalysis(TestCase):
    def setUp(self):
        self.analysis = Analysis(1)
        _, self.fp = get_mountpoint("analysis")[0]
        self.biom_fp = join(self.fp, "1_analysis_18S.biom")
        self.map_fp = join(self.fp, "1_analysis_mapping.txt")

    def tearDown(self):
        with open(self.biom_fp, 'w') as f:
                f.write("")
        with open(self.map_fp, 'w') as f:
                f.write("")

        fp = join(get_mountpoint('analysis')[0][1], 'testfile.txt')
        if exists(fp):
            remove(fp)

        mp = get_mountpoint("processed_data")[0][1]
        study2fp = join(mp, "2_2_study_1001_closed_reference_otu_table.biom")
        if exists(study2fp):
            move(study2fp,
                 join(mp, "2_study_1001_closed_reference_otu_table.biom"))

    def test_lock_check(self):
        for status in ["queued", "running", "public", "completed",
                       "error"]:
            new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                                  "A New Analysis")
            new.status = status
            with self.assertRaises(QiitaDBStatusError):
                new._lock_check(self.conn_handler)

    def test_lock_check_ok(self):
        self.analysis.status = "in_construction"
        self.analysis._lock_check(self.conn_handler)

    def test_status_setter_checks(self):
        self.analysis.status = "public"
        with self.assertRaises(QiitaDBStatusError):
            self.analysis.status = "queued"

    def test_get_by_status(self):
        self.assertEqual(Analysis.get_by_status('public'), [])
        self.analysis.status = "public"
        self.assertEqual(Analysis.get_by_status('public'), [1])

    def test_has_access_public(self):
        self.conn_handler.execute("UPDATE qiita.analysis SET "
                                  "analysis_status_id = 6")
        self.assertTrue(self.analysis.has_access(User("demo@microbio.me")))

    def test_has_access_shared(self):
        self.assertTrue(self.analysis.has_access(User("shared@foo.bar")))

    def test_has_access_private(self):
        self.assertTrue(self.analysis.has_access(User("test@foo.bar")))

    def test_has_access_admin(self):
        self.assertTrue(self.analysis.has_access(User("admin@foo.bar")))

    def test_has_access_no_access(self):
        self.assertFalse(self.analysis.has_access(User("demo@microbio.me")))

    def test_create(self):
        sql = "SELECT EXTRACT(EPOCH FROM NOW())"
        time1 = float(self.conn_handler.execute_fetchall(sql)[0][0])

        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis")
        self.assertEqual(new.id, 3)
        sql = ("SELECT analysis_id, email, name, description, "
               "analysis_status_id, pmid, EXTRACT(EPOCH FROM timestamp) "
               "FROM qiita.analysis WHERE analysis_id = 3")
        obs = self.conn_handler.execute_fetchall(sql)
        self.assertEqual(obs[0][:-1], [3, 'admin@foo.bar', 'newAnalysis',
                                       'A New Analysis', 1, None])
        self.assertTrue(time1 < float(obs[0][-1]))

    def test_create_parent(self):
        sql = "SELECT EXTRACT(EPOCH FROM NOW())"
        time1 = float(self.conn_handler.execute_fetchall(sql)[0][0])

        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        self.assertEqual(new.id, 3)
        sql = ("SELECT analysis_id, email, name, description, "
               "analysis_status_id, pmid, EXTRACT(EPOCH FROM timestamp) "
               "FROM qiita.analysis WHERE analysis_id = 3")
        obs = self.conn_handler.execute_fetchall(sql)
        self.assertEqual(obs[0][:-1], [3, 'admin@foo.bar', 'newAnalysis',
                                       'A New Analysis', 1, None])
        self.assertTrue(time1 < float(obs[0][-1]))

        sql = "SELECT * FROM qiita.analysis_chain WHERE child_id = 3"
        obs = self.conn_handler.execute_fetchall(sql)
        self.assertEqual(obs, [[1, 3]])

    def test_retrieve_owner(self):
        self.assertEqual(self.analysis.owner, "test@foo.bar")

    def test_retrieve_name(self):
        self.assertEqual(self.analysis.name, "SomeAnalysis")

    def test_retrieve_description(self):
        self.assertEqual(self.analysis.description, "A test analysis")

    def test_set_description(self):
        self.analysis.description = "New description"
        self.assertEqual(self.analysis.description, "New description")

    def test_retrieve_samples(self):
        exp = {1: ['1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196',
                   '1.SKM9.640192', '1.SKM4.640180']}
        self.assertEqual(self.analysis.samples, exp)

    def test_retrieve_dropped_samples(self):
        # Create and populate second study to do test with
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
        metadata_dict = {
            'SKB8.640193': {'physical_location': 'location1',
                            'has_physical_specimen': True,
                            'has_extracted_data': True,
                            'sample_type': 'type1',
                            'required_sample_info_status': 'received',
                            'collection_timestamp':
                            datetime(2014, 5, 29, 12, 24, 51),
                            'host_subject_id': 'NotIdentified',
                            'Description': 'Test Sample 1',
                            'str_column': 'Value for sample 1',
                            'latitude': 42.42,
                            'longitude': 41.41},
            'SKD8.640184': {'physical_location': 'location1',
                            'has_physical_specimen': True,
                            'has_extracted_data': True,
                            'sample_type': 'type1',
                            'required_sample_info_status': 'received',
                            'collection_timestamp':
                            datetime(2014, 5, 29, 12, 24, 51),
                            'host_subject_id': 'NotIdentified',
                            'Description': 'Test Sample 2',
                            'str_column': 'Value for sample 2',
                            'latitude': 4.2,
                            'longitude': 1.1},
            'SKB7.640196': {'physical_location': 'location1',
                            'has_physical_specimen': True,
                            'has_extracted_data': True,
                            'sample_type': 'type1',
                            'required_sample_info_status': 'received',
                            'collection_timestamp':
                            datetime(2014, 5, 29, 12, 24, 51),
                            'host_subject_id': 'NotIdentified',
                            'Description': 'Test Sample 3',
                            'str_column': 'Value for sample 3',
                            'latitude': 4.8,
                            'longitude': 4.41},
            }
        metadata = pd.DataFrame.from_dict(metadata_dict, orient='index')

        Study.create(User("test@foo.bar"), "Test study 2", [1], info)

        SampleTemplate.create(metadata, Study(2))

        mp = get_mountpoint("processed_data")[0][1]
        study_fp = join(mp, "2_study_1001_closed_reference_otu_table.biom")
        ProcessedData.create("processed_params_uclust", 1, [(study_fp, 6)],
                             study=Study(2), data_type="16S")
        self.conn_handler.execute(
            "INSERT INTO qiita.analysis_sample (analysis_id, "
            "processed_data_id, sample_id) VALUES "
            "(1,2,'2.SKB8.640193'), (1,2,'2.SKD8.640184'), "
            "(1,2,'2.SKB7.640196')")

        samples = {1: ['1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196'],
                   2: ['2.SKB8.640193', '2.SKD8.640184']}
        self.analysis._build_biom_tables(samples, 10000,
                                         conn_handler=self.conn_handler)
        exp = {1: {'1.SKM4.640180', '1.SKM9.640192'},
               2: {'2.SKB7.640196'}}
        self.assertEqual(self.analysis.dropped_samples, exp)

    def test_retrieve_data_types(self):
        exp = ['18S']
        self.assertEqual(self.analysis.data_types, exp)

    def test_retrieve_shared_with(self):
        self.assertEqual(self.analysis.shared_with, ["shared@foo.bar"])

    def test_retrieve_biom_tables(self):
        exp = {"18S": join(self.fp, "1_analysis_18S.biom")}
        self.assertEqual(self.analysis.biom_tables, exp)

    def test_all_associated_filepaths(self):
        exp = {12, 13, 14, 15}
        self.assertEqual(self.analysis.all_associated_filepath_ids, exp)

    def test_retrieve_biom_tables_none(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        self.assertEqual(new.biom_tables, None)

    def test_set_step(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        new.step = 2
        sql = "SELECT * FROM qiita.analysis_workflow WHERE analysis_id = 3"
        obs = self.conn_handler.execute_fetchall(sql)
        self.assertEqual(obs, [[3, 2]])

    def test_set_step_twice(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        new.step = 2
        new.step = 4
        sql = "SELECT * FROM qiita.analysis_workflow WHERE analysis_id = 3"
        obs = self.conn_handler.execute_fetchall(sql)
        self.assertEqual(obs, [[3, 4]])

    def test_retrieve_step(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        new.step = 2
        self.assertEqual(new.step, 2)

    def test_retrieve_step_new(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        with self.assertRaises(ValueError):
            new.step

    def test_retrieve_step_locked(self):
        self.analysis.status = "public"
        with self.assertRaises(QiitaDBStatusError):
            self.analysis.step = 3

    def test_retrieve_jobs(self):
        self.assertEqual(self.analysis.jobs, [1, 2])

    def test_retrieve_jobs_none(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        self.assertEqual(new.jobs, None)

    def test_retrieve_pmid(self):
        self.assertEqual(self.analysis.pmid, "121112")

    def test_retrieve_pmid_none(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        self.assertEqual(new.pmid, None)

    def test_set_pmid(self):
        self.analysis.pmid = "11211221212213"
        self.assertEqual(self.analysis.pmid, "11211221212213")

    def test_retrieve_mapping_file(self):
        exp = join(self.fp, "1_analysis_mapping.txt")
        obs = self.analysis.mapping_file
        self.assertEqual(obs, exp)
        self.assertTrue(exists(exp))

    def test_retrieve_mapping_file_none(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis", Analysis(1))
        obs = new.mapping_file
        self.assertEqual(obs, None)

    # def test_get_parent(self):
    #     raise NotImplementedError()

    # def test_get_children(self):
    #     raise NotImplementedError()

    def test_add_samples(self):
        new = Analysis.create(User("admin@foo.bar"), "newAnalysis",
                              "A New Analysis")
        new.add_samples([(1, '1.SKB8.640193'), (1, '1.SKD5.640186')])
        exp = {1: ['1.SKB8.640193', '1.SKD5.640186']}
        self.assertEqual(new.samples, exp)

    def test_remove_samples_both(self):
        self.analysis.remove_samples(proc_data=(1, ),
                                     samples=('1.SKB8.640193', ))
        exp = {1: ['1.SKD8.640184', '1.SKB7.640196', '1.SKM9.640192',
                   '1.SKM4.640180']}
        self.assertEqual(self.analysis.samples, exp)

    def test_remove_samples_samples(self):
        self.analysis.remove_samples(samples=('1.SKD8.640184', ))
        exp = {1: ['1.SKB8.640193', '1.SKB7.640196', '1.SKM9.640192',
                   '1.SKM4.640180']}
        self.assertEqual(self.analysis.samples, exp)

    def test_remove_samples_processed_data(self):
        self.analysis.remove_samples(proc_data=(1, ))
        exp = {}
        self.assertEqual(self.analysis.samples, exp)

    def test_share(self):
        self.analysis.share(User("admin@foo.bar"))
        self.assertEqual(self.analysis.shared_with, ["shared@foo.bar",
                                                     "admin@foo.bar"])

    def test_unshare(self):
        self.analysis.unshare(User("shared@foo.bar"))
        self.assertEqual(self.analysis.shared_with, [])

    def test_get_samples(self):
        obs = self.analysis._get_samples()
        exp = {1: ['1.SKB7.640196', '1.SKB8.640193', '1.SKD8.640184',
                   '1.SKM4.640180', '1.SKM9.640192']}
        self.assertEqual(obs, exp)

    def test_build_mapping_file(self):
        samples = {1: ['1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196']}
        self.analysis._build_mapping_file(samples,
                                          conn_handler=self.conn_handler)
        obs = self.analysis.mapping_file
        self.assertEqual(obs, self.map_fp)

        with open(self.map_fp) as f:
            mapdata = f.readlines()
        # check some columns for correctness
        obs = [line.split('\t')[0] for line in mapdata]
        exp = ['#SampleID', '1.SKB8.640193', '1.SKD8.640184',
               '1.SKB7.640196']
        self.assertEqual(obs, exp)

        obs = [line.split('\t')[1] for line in mapdata]
        exp = ['BarcodeSequence', 'AGCGCTCACATC', 'TGAGTGGTCTGT',
               'CGGCCTAAGTTC']
        self.assertEqual(obs, exp)

        obs = [line.split('\t')[2] for line in mapdata]
        exp = ['LinkerPrimerSequence', 'GTGCCAGCMGCCGCGGTAA',
               'GTGCCAGCMGCCGCGGTAA', 'GTGCCAGCMGCCGCGGTAA']
        self.assertEqual(obs, exp)

        obs = [line.split('\t')[19] for line in mapdata]
        exp = ['host_subject_id', '1001:M7', '1001:D9',
               '1001:M8']
        self.assertEqual(obs, exp)

        obs = [line.split('\t')[47] for line in mapdata]
        exp = ['tot_org_carb', '5.0', '4.32', '5.0']
        self.assertEqual(obs, exp)

        obs = [line.split('\t')[-1] for line in mapdata]
        exp = ['Description\n'] + ['Cannabis Soil Microbiome\n'] * 3
        self.assertEqual(obs, exp)

    def test_build_mapping_file_duplicate_samples(self):
        samples = {1: ['1.SKB8.640193', '1.SKB8.640193', '1.SKD8.640184']}
        with self.assertRaises(ValueError):
            self.analysis._build_mapping_file(samples,
                                              conn_handler=self.conn_handler)

    def test_build_biom_tables(self):
        samples = {1: ['1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196']}
        self.analysis._build_biom_tables(samples, 100,
                                         conn_handler=self.conn_handler)
        obs = self.analysis.biom_tables

        self.assertEqual(obs, {'18S': self.biom_fp})

        table = load_table(self.biom_fp)
        obs = set(table.ids(axis='sample'))
        exp = {'1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196'}
        self.assertEqual(obs, exp)

        obs = table.metadata('1.SKB8.640193')
        exp = {'Study':
               'Identification of the Microbiomes for Cannabis Soils',
               'Processed_id': 1}
        self.assertEqual(obs, exp)

    def test_build_files(self):
        self.analysis.build_files()

    def test_build_files_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.analysis.build_files('string')

        with self.assertRaises(TypeError):
            self.analysis.build_files(100.5)

    def test_build_files_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.analysis.build_files(0)

        with self.assertRaises(ValueError):
            self.analysis.build_files(-10)

    def test_add_file(self):
        fp = join(get_mountpoint('analysis')[0][1], 'testfile.txt')
        with open(fp, 'w') as f:
            f.write('testfile!')
        self.analysis._add_file('testfile.txt', 'plain_text', '18S')

        obs = self.conn_handler.execute_fetchall(
            'SELECT * FROM qiita.filepath WHERE filepath_id = 19')
        exp = [[19, 'testfile.txt', 9, '3675007573', 1, 1]]
        self.assertEqual(obs, exp)

        obs = self.conn_handler.execute_fetchall(
            'SELECT * FROM qiita.analysis_filepath WHERE filepath_id = 19')
        exp = [[1, 19, 2]]
        self.assertEqual(obs, exp)


@qiita_test_checker()
class TestCollection(TestCase):
    def setUp(self):
        self.collection = Collection(1)

    def test_create(self):
        Collection.create(User('test@foo.bar'), 'TestCollection2', 'Some desc')

        obs = self.conn_handler.execute_fetchall(
            'SELECT * FROM qiita.collection WHERE collection_id = 2')
        exp = [[2, 'test@foo.bar', 'TestCollection2', 'Some desc', 1]]
        self.assertEqual(obs, exp)

    def test_create_no_desc(self):
        Collection.create(User('test@foo.bar'), 'Test Collection2')

        obs = self.conn_handler.execute_fetchall(
            'SELECT * FROM qiita.collection WHERE collection_id = 2')
        exp = [[2, 'test@foo.bar', 'Test Collection2', None, 1]]
        self.assertEqual(obs, exp)

    def test_delete(self):
        Collection.delete(1)

        obs = self.conn_handler.execute_fetchall(
            'SELECT * FROM qiita.collection')
        exp = []
        self.assertEqual(obs, exp)

    def test_delete_public(self):
        self.collection.status = 'public'
        with self.assertRaises(QiitaDBStatusError):
            Collection.delete(1)

        obs = self.conn_handler.execute_fetchall(
            'SELECT * FROM qiita.collection')
        exp = [[1, 'test@foo.bar', 'TEST_COLLECTION',
                'collection for testing purposes', 2]]
        self.assertEqual(obs, exp)

    def test_retrieve_name(self):
        obs = self.collection.name
        exp = "TEST_COLLECTION"
        self.assertEqual(obs, exp)

    def test_set_name(self):
        self.collection.name = "NeW NaMe 123"
        self.assertEqual(self.collection.name, "NeW NaMe 123")

    def test_set_name_public(self):
        self.collection.status = "public"
        with self.assertRaises(QiitaDBStatusError):
            self.collection.name = "FAILBOAT"

    def test_retrieve_desc(self):
        obs = self.collection.description
        exp = "collection for testing purposes"
        self.assertEqual(obs, exp)

    def test_set_desc(self):
        self.collection.description = "NeW DeSc 123"
        self.assertEqual(self.collection.description, "NeW DeSc 123")

    def test_set_desc_public(self):
        self.collection.status = "public"
        with self.assertRaises(QiitaDBStatusError):
            self.collection.description = "FAILBOAT"

    def test_retrieve_owner(self):
        obs = self.collection.owner
        exp = "test@foo.bar"
        self.assertEqual(obs, exp)

    def test_retrieve_analyses(self):
        obs = self.collection.analyses
        exp = [1]
        self.assertEqual(obs, exp)

    def test_retrieve_highlights(self):
        obs = self.collection.highlights
        exp = [1]
        self.assertEqual(obs, exp)

    def test_retrieve_shared_with(self):
        obs = self.collection.shared_with
        exp = ["shared@foo.bar"]
        self.assertEqual(obs, exp)

    def test_add_analysis(self):
        self.collection.add_analysis(Analysis(2))
        obs = self.collection.analyses
        exp = [1, 2]
        self.assertEqual(obs, exp)

    def test_remove_analysis(self):
        self.collection.remove_analysis(Analysis(1))
        obs = self.collection.analyses
        exp = []
        self.assertEqual(obs, exp)

    def test_highlight_job(self):
        self.collection.highlight_job(Job(2))
        obs = self.collection.highlights
        exp = [1, 2]
        self.assertEqual(obs, exp)

    def test_remove_highlight(self):
        self.collection.remove_highlight(Job(1))
        obs = self.collection.highlights
        exp = []
        self.assertEqual(obs, exp)

    def test_share(self):
        self.collection.share(User("admin@foo.bar"))
        obs = self.collection.shared_with
        exp = ["shared@foo.bar", "admin@foo.bar"]
        self.assertEqual(obs, exp)

    def test_unshare(self):
        self.collection.unshare(User("shared@foo.bar"))
        obs = self.collection.shared_with
        exp = []
        self.assertEqual(obs, exp)


if __name__ == "__main__":
    main()
