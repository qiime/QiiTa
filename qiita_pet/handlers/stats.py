from __future__ import division

from random import choice

from moi import r_client
from tornado.gen import coroutine, Task

from qiita_db.util import get_count
from qiita_db.study import Study
from qiita_db.util import get_lat_longs
from .base_handlers import BaseHandler


class StatsHandler(BaseHandler):
    def _get_stats(self, callback):
        # check if the key exists in redis
        lats = r_client.lrange('stats:sample_lats', 0, -1)
        longs = r_client.lrange('stats:sample_longs', 0, -1)
        if not (lats or longs):
            # if we don't have them, then fetch from disk and add to the
            # redis server with a 24-hour expiration
            lat_longs = get_lat_longs()
            with r_client.pipeline() as pipe:
                for latitude, longitude in lat_longs:
                    # storing as a simple data structure, hopefully this
                    # doesn't burn us later
                    pipe.rpush('stats:sample_lats', latitude)
                    pipe.rpush('stats:sample_longs', longitude)

                # set the key to expire in 24 hours, so that we limit the
                # number of times we have to go to the database to a reasonable
                # amount
                r_client.expire('stats:sample_lats', 86400)
                r_client.expire('stats:sample_longs', 86400)

                pipe.execute()
        else:
            # If we do have them, put the redis results into the same structure
            # that would come back from the database
            longs = [float(x) for x in longs]
            lats = [float(x) for x in lats]
            lat_longs = zip(lats, longs)

        # Get the number of studies
        num_studies = get_count('qiita.study')

        # Get the number of samples
        num_samples = len(lats)

        # Get the number of users
        num_users = get_count('qiita.qiita_user')

        callback([num_studies, num_samples, num_users, lat_longs])

    @coroutine
    def get(self):
        num_studies, num_samples, num_users, lat_longs = \
            yield Task(self._get_stats)

        # Pull a random public study from the database
        public_studies = Study.get_by_status('public')
        study = Study(choice(public_studies)) if public_studies else None
        if study is None:
            random_study_info = None
            random_study_title = None
            random_study_id = None
        else:
            random_study_info = study.info
            random_study_title = study.title
            random_study_id = study.id

        self.render('stats.html',
                    num_studies=num_studies, num_samples=num_samples,
                    num_users=num_users, lat_longs=lat_longs,
                    random_study_info=random_study_info,
                    random_study_title=random_study_title,
                    random_study_id=random_study_id)
