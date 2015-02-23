# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main

from qiita_core.util import qiita_test_checker
from qiita_db.util import get_count, check_count


@qiita_test_checker()
class SetupTest(TestCase):
    """Tests that the test database have been successfully populated"""

    def test_qitta_user(self):
        self.assertEqual(get_count("qiita.qiita_user"), 4)

    def test_study_person(self):
        self.assertEqual(get_count("qiita.study_person"), 3)

    def test_study(self):
        self.assertEqual(get_count("qiita.study"), 1)

    def test_study_users(self):
        self.assertEqual(get_count("qiita.study_users"), 1)

    def test_investigation(self):
        self.assertEqual(get_count("qiita.investigation"), 1)

    def test_investigation_study(self):
        self.assertEqual(get_count("qiita.investigation_study"), 1)

    def test_study_experimental_factor(self):
        self.assertEqual(get_count("qiita.study_experimental_factor"), 1)

    def test_study_status(self):
        self.assertEqual(get_count("qiita.study_status"), 4)

    def test_filepath(self):
        self.assertEqual(get_count("qiita.filepath"), 18)

    def test_filepath_type(self):
        self.assertEqual(get_count("qiita.filepath_type"), 19)

    def test_raw_data(self):
        self.assertEqual(get_count("qiita.raw_data"), 4)

    def test_raw_filepath(self):
        self.assertEqual(get_count("qiita.raw_filepath"), 4)

    def test_study_raw_data(self):
        self.assertEqual(get_count("qiita.study_raw_data"), 4)

    def test_required_sample_info(self):
        self.assertEqual(get_count("qiita.required_sample_info"), 27)

    def test_study_sample_columns(self):
        self.assertEqual(get_count("qiita.study_sample_columns"), 21)

    def test_sample_1(self):
        self.assertEqual(get_count("qiita.sample_1"), 27)

    def test_prep_template(self):
        self.assertEqual(get_count("qiita.prep_template"), 1)

    def test_common_prep_info(self):
        self.assertEqual(get_count("qiita.common_prep_info"), 27)

    def test_prep_columns(self):
        self.assertEqual(get_count("qiita.prep_columns"), 19)

    def test_prep_1(self):
        self.assertEqual(get_count("qiita.prep_1"), 27)

    def test_preprocessed_data(self):
        self.assertEqual(get_count("qiita.preprocessed_data"), 2)

    def test_prep_template_preprocessed_data(self):
        self.assertEqual(get_count("qiita.prep_template_preprocessed_data"), 2)

    def test_study_preprocessed_data(self):
        self.assertEqual(get_count("qiita.study_preprocessed_data"), 2)

    def test_preprocessed_filepath(self):
        self.assertEqual(get_count("qiita.preprocessed_filepath"), 3)

    def test_preprocessed_sequence_illumina_params(self):
        self.assertEqual(
            get_count("qiita.preprocessed_sequence_illumina_params"), 6)

    def test_processed_data(self):
        self.assertEqual(get_count("qiita.processed_data"), 1)

    def test_preprocessed_processed_data(self):
        self.assertEqual(get_count("qiita.preprocessed_processed_data"), 1)

    def test_reference(self):
        self.assertEqual(get_count("qiita.reference"), 1)

    def test_processed_params_uclust(self):
        self.assertEqual(get_count("qiita.processed_params_uclust"), 1)

    def test_processed_filepath(self):
        self.assertEqual(get_count("qiita.processed_filepath"), 1)

    def test_job(self):
        self.assertEqual(get_count("qiita.job"), 3)

    def test_analysis(self):
        self.assertEqual(get_count("qiita.analysis"), 2)

    def test_analysis_job(self):
        self.assertEqual(get_count("qiita.analysis_job"), 3)

    def test_analysis_workflow(self):
        self.assertEqual(get_count("qiita.analysis_workflow"), 2)

    def test_analysis_filepath(self):
        self.assertEqual(get_count("qiita.analysis_filepath"), 2)

    def test_analysis_sample(self):
        self.assertEqual(get_count("qiita.analysis_sample"), 9)

    def test_analysis_users(self):
        self.assertEqual(get_count("qiita.analysis_users"), 1)

    def test_job_results_filepath(self):
        self.assertEqual(get_count("qiita.job_results_filepath"), 2)

    def test_command_data_type(self):
        self.assertEqual(get_count("qiita.command_data_type"), 14)

    def test_ontology(self):
        self.assertTrue(check_count('qiita.ontology', 1))

    def test_ontology_terms(self):
        self.assertTrue(check_count('qiita.term', 14))


if __name__ == '__main__':
    main()
