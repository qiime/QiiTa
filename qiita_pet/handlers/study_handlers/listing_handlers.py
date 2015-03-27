# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import division
from collections import namedtuple
from json import dumps
from future.utils import viewitems

from tornado.web import authenticated, HTTPError
from tornado.gen import coroutine, Task

from qiita_core.exceptions import IncompetentQiitaDeveloperError
from qiita_db.user import User
from qiita_db.study import Study, StudyPerson
from qiita_db.data import ProcessedData
from qiita_pet.handlers.base_handlers import BaseHandler
from qiita_pet.handlers.util import study_person_linkifier, pubmed_linkifier


def _get_shared_links_for_study(study):
    shared = []
    for person in study.shared_with:
        person = User(person)
        name = person.info['name']
        email = person.email
        # Name is optional, so default to email if non existant
        if name:
            shared.append(study_person_linkifier(
                (email, name)))
        else:
            shared.append(study_person_linkifier(
                (email, email)))
    return ", ".join(shared)


def _build_study_info(studytype, user=None):
    """builds list of namedtuples for study listings"""
    if studytype == "private":
        studylist = user.user_studies
    elif studytype == "shared":
        studylist = user.shared_studies
    elif studytype == "public":
        studylist = Study.get_by_status('public')
    else:
        raise IncompetentQiitaDeveloperError("Must use private, shared, "
                                             "or public!")

    StudyTuple = namedtuple('StudyInfo', 'id title meta_complete '
                            'num_samples_collected shared num_raw_data pi '
                            'pmids owner status abstract')

    infolist = []
    for s_id in studylist:
        study = Study(s_id)
        status = study.status
        # Just passing the email address as the name here, since
        # name is not a required field in qiita.qiita_user
        owner = study_person_linkifier((study.owner, study.owner))
        info = study.info
        PI = StudyPerson(info['principal_investigator_id'])
        PI = study_person_linkifier((PI.email, PI.name))
        pmids = ", ".join([pubmed_linkifier([pmid])
                           for pmid in study.pmids])
        shared = _get_shared_links_for_study(study)
        infolist.append(StudyTuple(study.id, study.title,
                                   info["metadata_complete"],
                                   info["number_samples_collected"],
                                   shared, len(study.raw_data()),
                                   PI, pmids, owner, status,
                                   info["study_abstract"]))
    return infolist


def _check_owner(user, study):
    """make sure user is the owner of the study requested"""
    if not user.id == study.owner:
        raise HTTPError(403, "User %s does not own study %d" %
                        (user.id, study.id))


class PrivateStudiesHandler(BaseHandler):
    @authenticated
    @coroutine
    def get(self):
        self.write(self.render_string('waiting.html'))
        self.flush()
        user = self.current_user
        user_studies = yield Task(self._get_private, user)
        shared_studies = yield Task(self._get_shared, user)
        all_emails_except_current = yield Task(self._get_all_emails)
        all_emails_except_current.remove(self.current_user.id)
        self.render('private_studies.html',
                    user_studies=user_studies, shared_studies=shared_studies,
                    all_emails_except_current=all_emails_except_current)

    def _get_private(self, user, callback):
        callback(_build_study_info("private", user))

    def _get_shared(self, user, callback):
        """builds list of tuples for studies that are shared with user"""
        callback(_build_study_info("shared", user))

    def _get_all_emails(self, callback):
        callback(list(User.iter()))


class PublicStudiesHandler(BaseHandler):
    @authenticated
    @coroutine
    def get(self):
        self.write(self.render_string('waiting.html'))
        self.flush()
        public_studies = yield Task(self._get_public)
        self.render('public_studies.html',
                    public_studies=public_studies)

    def _get_public(self, callback):
        """builds list of tuples for studies that are public"""
        callback(_build_study_info("public"))


class StudyApprovalList(BaseHandler):
    @authenticated
    def get(self):
        user = self.current_user
        if user.level != 'admin':
            raise HTTPError(403, 'User %s is not admin' % self.current_user)

        result_generator = viewitems(
            ProcessedData.get_by_status_grouped_by_study('awaiting_approval'))
        study_generator = ((Study(sid), pds) for sid, pds in result_generator)
        parsed_studies = [(s.id, s.title, s.owner, pds)
                          for s, pds in study_generator]

        self.render('admin_approval.html',
                    study_info=parsed_studies)


class ShareStudyAJAX(BaseHandler):
    def _get_shared_for_study(self, study, callback):
        shared_links = _get_shared_links_for_study(study)
        users = study.shared_with
        callback((users, shared_links))

    def _share(self, study, user, callback):
        user = User(user)
        callback(study.share(user))

    def _unshare(self, study, user, callback):
        user = User(user)
        callback(study.unshare(user))

    @authenticated
    @coroutine
    def get(self):
        study_id = int(self.get_argument('study_id'))
        study = Study(study_id)
        _check_owner(self.current_user, study)

        selected = self.get_argument('selected', None)
        deselected = self.get_argument('deselected', None)

        if selected is not None:
            yield Task(self._share, study, selected)
        if deselected is not None:
            yield Task(self._unshare, study, deselected)

        users, links = yield Task(self._get_shared_for_study, study)

        self.write(dumps({'users': users, 'links': links}))
