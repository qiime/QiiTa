from unittest import TestCase, main
from datetime import datetime
from os.path import join

from qiita_core.qiita_settings import qiita_config
from qiita_core.util import qiita_test_checker
from qiita_pet.handlers.api_proxy.artifact import (
    artifact_get_req, artifact_status_put_req, artifact_graph_get_req)


@qiita_test_checker()
class TestArtifactAPI(TestCase):
    def test_artifact_get_req(self):
        obs = artifact_get_req(1, 'test@foo.bar')
        exp = {'is_submitted_to_vamps': False,
               'data_type': '18S',
               'can_be_submitted_to_vamps': False,
               'can_be_submitted_to_ebi': False,
               'timestamp': datetime(2012, 10, 1, 9, 30, 27),
               'prep_templates': [1],
               'visibility': 'private',
               'study': 1,
               'processing_parameters': None,
               'ebi_run_accessions': None,
               'parents': [],
               'filepaths': [
                   (1, join(qiita_config.base_data_dir,
                            'raw_data/1_s_G1_L001_sequences.fastq.gz'),
                    'raw_forward_seqs'),
                   (2, join(qiita_config.base_data_dir,
                            'raw_data/1_s_G1_L001_sequences_barcodes.'
                            'fastq.gz'),
                    'raw_barcodes')],
               'artifact_type': 'FASTQ'}
        self.assertEqual(obs, exp)

    def test_artifact_get_req_no_access(self):
        obs = artifact_get_req(1, 'demo@microbio.me')
        exp = {'status': 'error',
               'message': 'User does not have access to study'}
        self.assertEqual(obs, exp)

    def test_artifact_status_put_req(self):
        obs = artifact_status_put_req(1, 'test@foo.bar', 'sandbox')
        exp = {'status': 'success',
               'message': 'Artifact visibility changed to sandbox'}
        self.assertEqual(obs, exp)

    def test_artifact_status_put_req_private(self):
        obs = artifact_status_put_req(1, 'admin@foo.bar', 'private')
        exp = {'status': 'success',
               'message': 'Artifact visibility changed to private'}
        self.assertEqual(obs, exp)

    def test_artifact_status_put_req_private_bad_permissions(self):
        obs = artifact_status_put_req(1, 'test@foo.bar', 'private')
        exp = {'status': 'error',
               'message': 'User does not have permissions to approve change'}
        self.assertEqual(obs, exp)

    def test_artifact_status_put_req_no_access(self):
        obs = artifact_status_put_req(1, 'demo@microbio.me', 'sandbox')
        exp = {'status': 'error',
               'message': 'User does not have access to study'}
        self.assertEqual(obs, exp)

    def test_artifact_graph_get_req_ancestors(self):
        obs = artifact_graph_get_req(1, 'ancestors', 'test@foo.bar')
        exp = {'node_labels': [(1, 'longer descriptive name for 1')],
               'edge_list': []}
        self.assertEqual(obs, exp)

    def test_artifact_graph_get_req_descendants(self):
        obs = artifact_graph_get_req(1, 'descendants', 'test@foo.bar')
        exp = {'node_labels': [(1, 'longer descriptive name for 1'),
                               (3, 'longer descriptive name for 3'),
                               (2, 'longer descriptive name for 2'),
                               (4, 'longer descriptive name for 4')],
               'edge_list': [(1, 3), (1, 2), (2, 4)]}
        self.assertEqual(obs, exp)

    def test_artifact_graph_get_req_no_access(self):
        obs = artifact_graph_get_req(1, 'ancestors', 'demo@microbio.me')
        exp = {'status': 'error',
               'message': 'User does not have access to study'}
        self.assertEqual(obs, exp)

    def test_artifact_graph_get_req_bad_direction(self):
        obs = artifact_graph_get_req(1, 'WRONG', 'test@foo.bar')
        exp = {'status': 'error', 'message': 'Unknown directon WRONG'}
        self.assertEqual(obs, exp)


if __name__ == '__main__':
    main()
