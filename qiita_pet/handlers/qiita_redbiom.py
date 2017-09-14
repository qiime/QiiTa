# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from requests import ConnectionError
from collections import defaultdict
import redbiom.summarize
import redbiom.search
import redbiom._requests
import redbiom.util
import redbiom.fetch
from tornado.gen import coroutine, Task

from qiita_core.util import execute_as_transaction
from qiita_db.util import generate_study_list_without_artifacts
from qiita_db.study import Study

from .base_handlers import BaseHandler


class RedbiomPublicSearch(BaseHandler):
    @execute_as_transaction
    def get(self, search):
        self.render('redbiom.html')

    def _redbiom_metadata_search(self, query, contexts):
        study_artifacts = defaultdict(list)
        message = ''
        query = query.lower()
        try:
            samples = redbiom.search.metadata_full(query, False)
        except TypeError:
            message = (
                'Not a valid search: "%s", are you sure this is a '
                'valid metadata value?' % query)
        except ValueError:
            message = (
                'Not a valid search: "%s", your query is too small '
                '(too few letters), try a longer query' % query)
        if not message:
            sids = set([s.split('.', 1)[0] for s in samples])
            for s in sids:
                study_artifacts[s] = [a.id for a in Study(s).artifacts(
                    artifact_type='BIOM')]

        return message, study_artifacts

    def _redbiom_feature_search(self, query, contexts):
        study_artifacts = defaultdict(list)
        query = [f for f in query.split(' ')]
        for ctx in contexts:
            for idx in redbiom.util.ids_from(query, True, 'feature', ctx):
                aid, sid = idx.split('_', 1)
                sid = sid.split('.', 1)[0]
                study_artifacts[sid].append(aid)

        return '', study_artifacts

    def _redbiom_taxon_search(self, query, contexts):
        study_artifacts = defaultdict(list)
        for ctx in contexts:
            # find the features with those taxonomies and then search
            # those features in the samples
            features = redbiom.fetch.taxon_descendents(ctx, query)
            for idx in redbiom.util.ids_from(features, True, 'feature',
                                             ctx):
                aid, sid = idx.split('_', 1)
                sid = sid.split('.', 1)[0]
                study_artifacts[sid].append(aid)

        return '', study_artifacts

    @execute_as_transaction
    def _redbiom_search(self, query, search_on, callback):
        search_f = {'metadata': self._redbiom_metadata_search,
                    'feature': self._redbiom_feature_search,
                    'taxon': self._redbiom_taxon_search}

        message = ''
        results = []

        try:
            df = redbiom.summarize.contexts()
        except ConnectionError:
            message = 'Redbiom is down - contact admin, thanks!'
        else:
            contexts = df.ContextName.values
            if search_on in search_f:
                message, study_artifacts = search_f[search_on](query, contexts)
                if not message:
                    keys = study_artifacts.keys()
                    if keys:
                        results = generate_study_list_without_artifacts(
                            study_artifacts.keys(), True)
                        # inserting the artifact_biom_ids to the results
                        for i in range(len(results)):
                            results[i]['artifact_biom_ids'] = list(set(
                                study_artifacts[str(results[i]['study_id'])]))
                    else:
                        message = "No samples where found! Try again ..."
            else:
                message = ('Incorrect search by: you can use metadata, '
                           'features or taxon and you passed: %s' % search_on)

        callback((results, message))

    @coroutine
    @execute_as_transaction
    def post(self, search):
        search = self.get_argument('search')
        search_on = self.get_argument('search_on')

        data, msg = yield Task(self._redbiom_search, search, search_on)

        self.write({'status': 'success', 'message': msg, 'data': data})
