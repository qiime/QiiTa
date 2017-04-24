# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main
from json import loads

from tornado.web import HTTPError

from qiita_core.util import qiita_test_checker
from qiita_db.user import User
from qiita_db.analysis import Analysis
from qiita_pet.test.tornado_test_base import TestHandlerBase
from qiita_pet.handlers.analysis_handlers.base_handlers import (
    analyisis_graph_handler_get_request)


@qiita_test_checker()
class TestBaseHandlersUtils(TestCase):
    def test_analyisis_graph_handler_get_request(self):
        obs = analyisis_graph_handler_get_request(1, User('test@foo.bar'))
        # The job id is randomly generated in the test environment. Gather
        # it here. There is only 1 job in the first artifact of the analysis
        job_id = Analysis(1).artifacts[0].jobs()[0].id
        exp = {'edges': [(8, job_id), (job_id, 9)],
               'nodes': [('job', job_id, 'Single Rarefaction'),
                         ('artifact', 9, 'noname - BIOM'),
                         ('artifact', 8, 'noname - BIOM')]}
        self.assertItemsEqual(obs, exp)
        self.assertItemsEqual(obs['edges'], exp['edges'])
        self.assertItemsEqual(obs['nodes'], exp['nodes'])

        # An admin has full access to the analysis
        obs = analyisis_graph_handler_get_request(1, User('admin@foo.bar'))
        self.assertItemsEqual(obs, exp)
        self.assertItemsEqual(obs['edges'], exp['edges'])
        self.assertItemsEqual(obs['nodes'], exp['nodes'])

        # If the analysis is shared with the user he also has access
        obs = analyisis_graph_handler_get_request(1, User('shared@foo.bar'))
        self.assertItemsEqual(obs, exp)
        self.assertItemsEqual(obs['edges'], exp['edges'])
        self.assertItemsEqual(obs['nodes'], exp['nodes'])

        # The user doesn't have access to the analysis
        with self.assertRaises(HTTPError):
            analyisis_graph_handler_get_request(1, User('demo@microbio.me'))


class TestBaseHandlers(TestHandlerBase):
    def test_post_create_analysis_handler(self):
        user = User('test@foo.bar')
        dflt_analysis = user.default_analysis
        dflt_analysis.add_samples(
            {4: ['1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196',
                 '1.SKM9.640192', '1.SKM4.640180']})
        args = {'name': 'New Test Analysis',
                'description': 'Test Analysis Description'}
        response = self.post('/analysis/create/', args)
        self.assertRegexpMatches(
            response.effective_url,
            r"http://localhost:\d+/analysis/description/\d+/")
        self.assertEqual(response.code, 200)

    def test_get_analysis_description_handler(self):
        response = self.get('/analysis/description/1/')
        self.assertEqual(response.code, 200)

    def test_get_analysis_graph_handler(self):
        response = self.get('/analysis/description/1/graph/')
        self.assertEqual(response.code, 200)
        # The job id is randomly generated in the test environment. Gather
        # it here. There is only 1 job in the first artifact of the analysis
        job_id = Analysis(1).artifacts[0].jobs()[0].id
        obs = loads(response.body)
        exp = {'edges': [[8, job_id], [job_id, 9]],
               'nodes': [['job', job_id, 'Single Rarefaction'],
                         ['artifact', 9, 'noname - BIOM'],
                         ['artifact', 8, 'noname - BIOM']]}
        self.assertItemsEqual(obs, exp)
        self.assertItemsEqual(obs['edges'], exp['edges'])
        self.assertItemsEqual(obs['nodes'], exp['nodes'])

    def test_get_analysis_jobs_handler(self):
        user = User('test@foo.bar')
        dflt_analysis = user.default_analysis
        dflt_analysis.add_samples(
            {4: ['1.SKB8.640193', '1.SKD8.640184', '1.SKB7.640196',
                 '1.SKM9.640192', '1.SKM4.640180']})
        new = Analysis.create(user, "newAnalysis", "A New Analysis",
                              from_default=True)
        response = self.get('/analysis/description/%s/jobs/' % new.id)
        self.assertEqual(response.code, 200)

        # There is only one job
        job_id = new.jobs[0].id
        obs = loads(response.body)
        exp = {job_id: {'status': 'queued', 'step': None, 'error': ""}}
        self.assertEqual(obs, exp)


if __name__ == '__main__':
    main()
