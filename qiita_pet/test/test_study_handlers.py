from unittest import TestCase, main

from tornado_test_base import TestHandlerBase
from qiita_db.study import StudyPerson
from qiita_db.util import get_count, check_count
from study_handlers import (
    _build_study_info, _check_access, CreateStudyForm, PrivateStudiesHandler,
    PublicStudiesHandler, StudyDescriptionHandler, CreateStudyHandler,
    CreateStudyAJAX, MetadataSummaryHandler, EBISubmitHandler)


class TestCreateStudyForm(TestHandlerBase):
    # TODO: add tests for form creation
    pass


class TestPrivateStudiesHandler(TestCase):
    def test_get(self):
        raise NotImplementedError()

    def test__get_private(self):
        raise NotImplementedError()

    def test__get_shared(self):
        raise NotImplementedError()

    def test_post(self):
        raise NotImplementedError()


class TestPublicStudiesHandler(TestCase):
    def test_get(self):
        raise NotImplementedError()

    def test_get_public(self):
        raise NotImplementedError()

    def test_post(self):
        raise NotImplementedError()


class TestStudyDescriptionHandler(TestCase):
    def test_display_template(self):
        raise NotImplementedError()

    def test_get(self):
        raise NotImplementedError()

    def test_post(self):
        raise NotImplementedError()


class TestCreateStudyHandler(TestCase):
    def test_get(self):
        """Make sure the page loads when no arguments are passed"""
        response = self.get('/study/create/')
        self.assertEqual(response.code, 200)

    def test_post(self):
        person_count_before = get_count('qiita.study_person')

        post_data = {'new_people_names': ['Adam', 'Ethan'],
                     'new_people_emails': ['a@mail.com', 'e@mail.com'],
                     'new_people_affiliations': ['CU Boulder', 'NYU'],
                     'new_people_addresses': ['Some St., Boulder, CO 80305',
                                              ''],
                     'new_people_phones': ['', ''],
                     'study_title': 'dummy title',
                     'study_alias': 'dummy alias',
                     'pubmed_id': 'dummy pmid',
                     'investigation_type': 'eukaryote',
                     'environmental_packages': 'air',
                     'is_timeseries': 'y',
                     'study_abstract': "dummy abstract",
                     'study_description': 'dummy description',
                     'principal_investigator': '-2',
                     'lab_person': '1'}

        self.post('/study/create/', post_data)

        # Check that the new person was created
        expected_id = person_count_before + 1
        self.assertTrue(check_count('qiita.study_person', expected_id))

        new_person = StudyPerson(expected_id)
        self.assertTrue(new_person.name == 'Ethan')
        self.assertTrue(new_person.email == 'e@mail.com')
        self.assertTrue(new_person.affiliation == 'NYU')
        self.assertTrue(new_person.address is None)
        self.assertTrue(new_person.phone is None)


class TestCreateStudyAJAX(TestCase):
    def test_get(self):
        raise NotImplementedError()


class TestMetadataSummaryHandler(TestCase):
    def test_get(self):
        raise NotImplementedError()


class TestEBISubmitHandler(TestCase):
    def test_get(self):
        raise NotImplementedError()

    def test_get(self):
        raise NotImplementedError()

    def test_post(self):
        raise NotImplementedError()


if __name__ == "__main__":
    main()
