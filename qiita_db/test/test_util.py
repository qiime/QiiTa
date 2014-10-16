# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main
from tempfile import mkstemp
from os import close, remove
from os.path import join, exists, basename

from qiita_core.util import qiita_test_checker
from qiita_core.exceptions import IncompetentQiitaDeveloperError
from qiita_db.exceptions import QiitaDBColumnError
from qiita_db.util import (exists_table, exists_dynamic_table, scrub_data,
                           compute_checksum, check_table_cols,
                           check_required_columns, convert_to_id,
                           get_table_cols, get_table_cols_w_type,
                           get_filetypes, get_filepath_types, get_count,
                           check_count, get_processed_params_tables,
                           params_dict_to_json, get_user_fp, get_study_fp,
                           insert_filepaths, get_db_files_base_dir,
                           get_data_types, get_required_sample_info_status,
                           get_emp_status)
from qiita_core.qiita_settings import qiita_config


@qiita_test_checker()
class DBUtilTests(TestCase):
    def setUp(self):
        self.table = 'study'
        self.required = [
            'number_samples_promised', 'study_title', 'mixs_compliant',
            'metadata_complete', 'study_description', 'first_contact',
            'reprocess', 'study_status_id', 'portal_type_id',
            'timeseries_type_id', 'study_alias', 'study_abstract',
            'principal_investigator_id', 'email', 'number_samples_collected']
        self.files_to_remove = []

    def tearDown(self):
        for fp in self.files_to_remove:
            if exists(fp):
                remove(fp)

    def test_params_dict_to_json(self):
        params_dict = {'opt1': '1', 'opt2': [2, '3'], 3: 9}
        exp = '{"3":9,"opt1":"1","opt2":[2,"3"]}'
        self.assertEqual(params_dict_to_json(params_dict), exp)

    def test_check_required_columns(self):
        # Doesn't do anything if correct info passed, only errors if wrong info
        check_required_columns(self.conn_handler, self.required, self.table)

    def test_check_required_columns_fail(self):
        self.required.remove('study_title')
        with self.assertRaises(QiitaDBColumnError):
            check_required_columns(self.conn_handler, self.required,
                                   self.table)

    def test_check_table_cols(self):
        # Doesn't do anything if correct info passed, only errors if wrong info
        check_table_cols(self.conn_handler, self.required, self.table)

    def test_check_table_cols_fail(self):
        self.required.append('BADTHINGNOINHERE')
        with self.assertRaises(QiitaDBColumnError):
            check_table_cols(self.conn_handler, self.required,
                             self.table)

    def test_get_table_cols(self):
        obs = get_table_cols("qiita_user", self.conn_handler)
        exp = {"email", "user_level_id", "password", "name", "affiliation",
               "address", "phone", "user_verify_code", "pass_reset_code",
               "pass_reset_timestamp"}
        self.assertEqual(set(obs), exp)

    def test_get_table_cols_w_type(self):
        obs = get_table_cols_w_type("preprocessed_sequence_illumina_params",
                                    self.conn_handler)
        exp = [['preprocessed_params_id', 'bigint'],
               ['max_bad_run_length', 'integer'],
               ['min_per_read_length_fraction', 'real'],
               ['sequence_max_n', 'integer'],
               ['rev_comp_barcode', 'boolean'],
               ['rev_comp_mapping_barcodes', 'boolean'],
               ['rev_comp', 'boolean'],
               ['phred_quality_threshold', 'integer'],
               ['barcode_type', 'character varying'],
               ['max_barcode_errors', 'real']]
        self.assertItemsEqual(obs, exp)

    def test_exists_table(self):
        """Correctly checks if a table exists"""
        # True cases
        self.assertTrue(exists_table("filepath", self.conn_handler))
        self.assertTrue(exists_table("qiita_user", self.conn_handler))
        self.assertTrue(exists_table("analysis", self.conn_handler))
        self.assertTrue(exists_table("prep_1", self.conn_handler))
        self.assertTrue(exists_table("sample_1", self.conn_handler))
        # False cases
        self.assertFalse(exists_table("sample_2", self.conn_handler))
        self.assertFalse(exists_table("prep_2", self.conn_handler))
        self.assertFalse(exists_table("foo_table", self.conn_handler))
        self.assertFalse(exists_table("bar_table", self.conn_handler))

    def test_exists_dynamic_table(self):
        """Correctly checks if a dynamic table exists"""
        # True cases
        self.assertTrue(exists_dynamic_table(
            "preprocessed_sequence_illumina_params", "preprocessed_",
            "_params", self.conn_handler))
        self.assertTrue(exists_dynamic_table("prep_1", "prep_", "",
                                             self.conn_handler))
        self.assertTrue(exists_dynamic_table("filepath", "", "",
                                             self.conn_handler))
        # False cases
        self.assertFalse(exists_dynamic_table(
            "preprocessed_foo_params", "preprocessed_", "_params",
            self.conn_handler))
        self.assertFalse(exists_dynamic_table(
            "preprocessed__params", "preprocessed_", "_params",
            self.conn_handler))
        self.assertFalse(exists_dynamic_table(
            "foo_params", "preprocessed_", "_params",
            self.conn_handler))
        self.assertFalse(exists_dynamic_table(
            "preprocessed_foo", "preprocessed_", "_params",
            self.conn_handler))
        self.assertFalse(exists_dynamic_table(
            "foo", "preprocessed_", "_params",
            self.conn_handler))

    def test_convert_to_id(self):
        """Tests that ids are returned correctly"""
        self.assertEqual(convert_to_id("directory", "filepath_type"), 8)

    def test_convert_to_id_bad_value(self):
        """Tests that ids are returned correctly"""
        with self.assertRaises(IncompetentQiitaDeveloperError):
            convert_to_id("FAKE", "filepath_type")

    def test_get_filetypes(self):
        """Tests that get_filetypes works with valid arguments"""

        obs = get_filetypes()
        exp = {'FASTA': 1, 'FASTQ': 2, 'SPECTRA': 3}
        self.assertEqual(obs, exp)

        obs = get_filetypes(key='filetype_id')
        exp = {v: k for k, v in exp.items()}
        self.assertEqual(obs, exp)

    def test_get_filetypes_fail(self):
        """Tests that get_Filetypes fails with invalid argument"""
        with self.assertRaises(QiitaDBColumnError):
            get_filetypes(key='invalid')

    def test_get_filepath_types(self):
        """Tests that get_filepath_types works with valid arguments"""
        obs = get_filepath_types()
        exp = {'raw_forward_seqs': 1, 'raw_reverse_seqs': 2,
               'raw_barcodes': 3, 'preprocessed_fasta': 4,
               'preprocessed_fastq': 5, 'preprocessed_demux': 6, 'biom': 7,
               'directory': 8, 'plain_text': 9, 'reference_seqs': 10,
               'reference_tax': 11, 'reference_tree': 12, 'log': 13}
        self.assertEqual(obs, exp)

        obs = get_filepath_types(key='filepath_type_id')
        exp = {v: k for k, v in exp.items()}
        self.assertEqual(obs, exp)

    def test_get_filepath_types_fail(self):
        """Tests that get_Filetypes fails with invalid argument"""
        with self.assertRaises(QiitaDBColumnError):
            get_filepath_types(key='invalid')

    def test_get_data_types(self):
        """Tests that get_data_types works with valid arguments"""
        obs = get_data_types()
        exp = {'16S': 1, '18S': 2, 'ITS': 3, 'Proteomic': 4, 'Metabolomic': 5,
               'Metagenomic': 6}
        self.assertEqual(obs, exp)

        obs = get_data_types(key='data_type_id')
        exp = {v: k for k, v in exp.items()}
        self.assertEqual(obs, exp)

    def test_get_required_sample_info_status(self):
        """Tests that get_required_sample_info_status works"""
        obs = get_required_sample_info_status()
        exp = {'received': 1, 'in_preparation': 2, 'running': 3,
               'completed': 4}
        self.assertEqual(obs, exp)

        obs = get_required_sample_info_status(
            key='required_sample_info_status_id')
        exp = {v: k for k, v in exp.items()}
        self.assertEqual(obs, exp)

    def test_get_emp_status(self):
        """Tests that get_emp_status works"""
        obs = get_emp_status()
        exp = {'EMP': 1, 'EMP_Processed': 2, 'NOT_EMP': 3}
        self.assertEqual(obs, exp)

        obs = get_emp_status(key='emp_status_id')
        exp = {v: k for k, v in exp.items()}
        self.assertEqual(obs, exp)

    def test_get_count(self):
        """Checks that get_count retrieves proper count"""
        self.assertEqual(get_count('qiita.study_person'), 3)

    def test_check_count(self):
        """Checks that check_count returns True and False appropriately"""
        self.assertTrue(check_count('qiita.study_person', 3))
        self.assertFalse(check_count('qiita.study_person', 2))

    def test_get_processed_params_tables(self):
        obs = get_processed_params_tables()
        self.assertEqual(obs, ['processed_params_sortmerna',
                               'processed_params_uclust'])

    def test_get_user_fps(self):
        obs = get_user_fp("demo@demo.com")
        exp = join(qiita_config.upload_data_dir, 'demo.com', 'demo')
        self.assertEqual(obs, exp)

    def test_insert_filepaths(self):
        fd, fp = mkstemp()
        close(fd)
        with open(fp, "w") as f:
            f.write("\n")
        self.files_to_remove.append(fp)

        obs = insert_filepaths([(fp, 1)], 1, "raw_data", "filepath",
                               self.conn_handler)
        exp = [16]
        self.assertEqual(obs, exp)

        # Check that the files have been copied correctly
        exp_fp = join(get_db_files_base_dir(), "raw_data",
                      "1_%s" % basename(fp))
        self.assertTrue(exists(exp_fp))
        self.files_to_remove.append(exp_fp)

        # Check that the filepaths have been added to the DB
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.filepath WHERE filepath_id=16")
        exp_fp = join("raw_data", "1_%s" % basename(fp))
        exp = [[16, exp_fp, 1, '852952723', 1]]
        self.assertEqual(obs, exp)

    def test_insert_filepaths_string(self):
        fd, fp = mkstemp()
        close(fd)
        with open(fp, "w") as f:
            f.write("\n")
        self.files_to_remove.append(fp)

        obs = insert_filepaths([(fp, "raw_forward_seqs")], 1, "raw_data",
                               "filepath", self.conn_handler)
        exp = [16]
        self.assertEqual(obs, exp)

        # Check that the files have been copied correctly
        exp_fp = join(get_db_files_base_dir(), "raw_data",
                      "1_%s" % basename(fp))
        self.assertTrue(exists(exp_fp))
        self.files_to_remove.append(exp_fp)

        # Check that the filepaths have been added to the DB
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.filepath WHERE filepath_id=16")
        exp_fp = join("raw_data", "1_%s" % basename(fp))
        exp = [[16, exp_fp, 1, '852952723', 1]]
        self.assertEqual(obs, exp)

    def test_get_study_fps(self):
        study_id = 1000
        obs = get_study_fp(study_id)
        exp = join(qiita_config.upload_data_dir, str(study_id))
        self.assertEqual(obs, exp)


class UtilTests(TestCase):
    """Tests for the util functions that do not need to access the DB"""

    def setUp(self):
        fh, self.filepath = mkstemp()
        close(fh)
        with open(self.filepath, "w") as f:
            f.write("Some text so we can actually compute a checksum")

    def test_compute_checksum(self):
        """Correctly returns the file checksum"""
        obs = compute_checksum(self.filepath)
        exp = 1719580229
        self.assertEqual(obs, exp)

    def test_scrub_data_nothing(self):
        """Returns the same string without changes"""
        self.assertEqual(scrub_data("nothing_changes"), "nothing_changes")

    def test_scrub_data_semicolon(self):
        """Correctly removes the semicolon from the string"""
        self.assertEqual(scrub_data("remove_;_char"), "remove__char")

    def test_scrub_data_single_quote(self):
        """Correctly removes single quotes from the string"""
        self.assertEqual(scrub_data("'quotes'"), "quotes")

if __name__ == '__main__':
    main()
