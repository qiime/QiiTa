# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main
from os.path import exists
from os import close, remove
from tempfile import mkstemp

import pandas as pd

from qiita_core.util import qiita_test_checker
from qiita_db.software import Software, Parameters
from qiita_db.processing_job import ProcessingJob
from qiita_db.user import User
from qiita_db.study import Study, StudyPerson
from qiita_db.metadata_template.sample_template import SampleTemplate
from qiita_db.metadata_template.prep_template import PrepTemplate
from qiita_ware.private_plugin import private_task


@qiita_test_checker()
class TestPrivatePlugin(TestCase):
    def setUp(self):
        self._clean_up_files = []

    def tearDown(self):
        for fp in self._clean_up_files:
            if exists(fp):
                remove(fp)

    def _create_job(self, cmd_name, values_dict):
        user = User('test@foo.bar')
        qiita_plugin = Software.from_name_and_version('Qiita', 'alpha')
        cmd = qiita_plugin.get_command(cmd_name)
        params = Parameters.load(cmd, values_dict=values_dict)
        job = ProcessingJob.create(user, params)
        job._set_status('queued')
        return job

    def test_copy_artifact(self):
        # Failure test
        job = self._create_job('copy_artifact',
                               {'artifact': 1, 'prep_template': 1})

        private_task(job.id)
        self.assertEqual(job.status, 'error')
        self.assertIn("Prep template 1 already has an artifact associated",
                      job.log.msg)

        # Success test
        metadata_dict = {
            'SKB8.640193': {'center_name': 'ANL',
                            'primer': 'GTGCCAGCMGCCGCGGTAA',
                            'barcode': 'GTCCGCAAGTTA',
                            'run_prefix': "s_G1_L001_sequences",
                            'platform': 'ILLUMINA',
                            'instrument_model': 'Illumina MiSeq',
                            'library_construction_protocol': 'AAAA',
                            'experiment_design_description': 'BBBB'}}
        metadata = pd.DataFrame.from_dict(metadata_dict, orient='index',
                                          dtype=str)
        prep = PrepTemplate.create(metadata, Study(1), "16S")
        job = self._create_job('copy_artifact', {'artifact': 1,
                                                 'prep_template': prep.id})
        private_task(job.id)
        self.assertEqual(job.status, 'success')

    def test_update_sample_template(self):
        fd, fp = mkstemp(suffix=".txt")
        close(fd)
        with open(fp, 'w') as f:
            f.write("sample_name\tnew_col\n1.SKD6.640190\tnew_value")
        self._clean_up_files.append(fp)

        job = self._create_job('update_sample_template',
                               {'study': 1, 'template_fp': fp})
        private_task(job.id)
        self.assertEqual(job.status, 'success')
        self.assertEqual(SampleTemplate(1)['1.SKD6.640190']['new_col'],
                         'new_value')

        # TODO: Check that redis has been updated with:
        "Sample names were already prefixed with the study "
        "id.\nThe following columns have been added to the "
        "existing template: new_col\nThere are no "
        "differences between the data stored in the DB and "
        "the new data provided"

    def test_delete_sample_template(self):
        # Error case
        job = self._create_job('delete_sample_template', {'study': 1})
        private_task(job.id)
        self.assertEqual(job.status, 'error')
        self.assertIn("Sample template cannot be erased because there are "
                      "prep templates associated", job.log.msg)

        # Success case
        info = {"timeseries_type_id": '1',
                "metadata_complete": 'true',
                "mixs_compliant": 'true',
                "number_samples_collected": 25,
                "number_samples_promised": 28,
                "study_alias": "TDST",
                "study_description": "Test delete sample template",
                "study_abstract": "Test delete sample template",
                "principal_investigator_id": StudyPerson(1)}
        study = Study.create(User('test@foo.bar'),
                             "Delete Sample Template test", info)
        metadata = pd.DataFrame.from_dict(
            {'Sample1': {'physical_specimen_location': 'location1',
                         'physical_specimen_remaining': 'true',
                         'dna_extracted': 'true',
                         'sample_type': 'type1',
                         'collection_timestamp': '2014-05-29 12:24:15',
                         'host_subject_id': 'NotIdentified',
                         'Description': 'Test Sample 1',
                         'latitude': '42.42',
                         'longitude': '41.41',
                         'taxon_id': '9606',
                         'scientific_name': 'homo sapiens'}},
            orient='index', dtype=str)
        SampleTemplate.create(metadata, study)

        job = self._create_job('delete_sample_template', {'study': study.id})
        private_task(job.id)
        self.assertEqual(job.status, 'success')
        self.assertFalse(SampleTemplate.exists(study.id))

    def test_update_prep_template(self):
        fd, fp = mkstemp(suffix=".txt")
        close(fd)
        with open(fp, 'w') as f:
            f.write("sample_name\tnew_col\n1.SKD6.640190\tnew_value")
        job = self._create_job('update_prep_template', {'prep_template': 1,
                                                        'template_fp': fp})
        private_task(job.id)
        self.assertEqual(job.status, 'success')
        self.assertEqual(PrepTemplate(1)['1.SKD6.640190']['new_col'],
                         'new_value')

        # TODO: Check that redis has been updated with:
        'Sample names were already prefixed with the study '
        'id.\nThe following columns have been added to the '
        'existing template: new_col\nThere are no '
        'differences between the data stored in the DB and '
        'the new data provided'


if __name__ == '__main__':
    main()
