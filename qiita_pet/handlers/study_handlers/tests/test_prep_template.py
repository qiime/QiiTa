# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from unittest import main
from json import loads
from time import sleep

from qiita_pet.test.tornado_test_base import TestHandlerBase


class TestNewPrepTemplateAjax(TestHandlerBase):
    def test_get(self):
        response = self.get('/study/new_prep_template/', {'study_id': '1'})
        self.assertEqual(response.code, 200)


class TestPrepTemplateGraphAJAX(TestHandlerBase):
    def test_get(self):
        response = self.get('/prep/graph/', {'prep_id': 1})
        self.assertEqual(response.code, 200)

        # job ids are generated by random so testing composition
        obs = loads(response.body)
        self.assertEqual(obs['message'], '')
        self.assertEqual(obs['status'], 'success')

        self.assertEqual(11, len(obs['node_labels']))
        self.assertIn(['artifact', 1, 'Raw data 1 - FASTQ'],
                      obs['node_labels'])
        self.assertIn(['artifact', 2, 'Demultiplexed 1 - Demultiplexed'],
                      obs['node_labels'])
        self.assertIn(['artifact', 3, 'Demultiplexed 2 - Demultiplexed'],
                      obs['node_labels'])
        self.assertIn(['artifact', 4, 'BIOM - BIOM'],
                      obs['node_labels'])
        self.assertIn(['artifact', 5, 'BIOM - BIOM'],
                      obs['node_labels'])
        self.assertIn(['artifact', 6, 'BIOM - BIOM'],
                      obs['node_labels'])
        self.assertEqual(3, len([n for dt, _, n in obs['node_labels']
                                 if n == 'Pick closed-reference OTUs' and
                                 dt == 'job']))
        self.assertEqual(2, len([n for dt, _, n in obs['node_labels']
                                 if n == 'Split libraries FASTQ' and
                                 dt == 'job']))

        self.assertEqual(10, len(obs['edge_list']))
        self.assertEqual(2, len([x for x, y in obs['edge_list'] if x == 1]))
        self.assertEqual(3, len([x for x, y in obs['edge_list'] if x == 2]))
        self.assertEqual(1, len([x for x, y in obs['edge_list'] if y == 2]))
        self.assertEqual(1, len([x for x, y in obs['edge_list'] if y == 3]))
        self.assertEqual(1, len([x for x, y in obs['edge_list'] if y == 4]))
        self.assertEqual(1, len([x for x, y in obs['edge_list'] if y == 5]))
        self.assertEqual(1, len([x for x, y in obs['edge_list'] if y == 6]))


class TestPrepTemplateAJAXReadOnly(TestHandlerBase):
    def test_get(self):
        response = self.get('/study/description/prep_template/',
                            {'prep_id': 1, 'study_id': 1})
        self.assertEqual(response.code, 200)
        self.assertNotEqual(response.body, '')


class TestPrepFilesHandler(TestHandlerBase):
    def test_get_files_not_allowed(self):
        response = self.post(
            '/study/prep_files/',
            {'type': 'BIOM', 'prep_file': 'uploaded_file.txt', 'study_id': 1})
        self.assertEqual(response.code, 405)


if __name__ == "__main__":
    main()
