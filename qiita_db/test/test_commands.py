# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main
from future.utils.six import StringIO
from os.path import join, dirname
try:
    # Python 2
    from ConfigParser import NoOptionError
except ImportError:
    # Python 3
    from configparser import NoOptionError

from qiita_db.study import Study, StudyPerson
from qiita_db.user import User
from qiita_core.util import qiita_test_checker
from qiita_db.commands import make_study_from_cmd, sample_template_adder


@qiita_test_checker()
class TestMakeStudyFromCmd(TestCase):
    def setUp(self):
        StudyPerson.create('SomeDude', 'somedude@foo.bar',
                           '111 fake street', '111-121-1313')
        User.create('test@test.com', 'password')
        self.config1 = CONFIG_1
        self.config2 = CONFIG_2

    def test_make_study_from_cmd(self):
        fh = StringIO(self.config1)
        make_study_from_cmd('test@test.com', 'newstudy', fh)
        sql = ("select study_id from qiita.study where email = %s and "
               "study_title = %s")
        study_id = self.conn_handler.execute_fetchone(sql, ('test@test.com',
                                                            'newstudy'))
        self.assertTrue(study_id is not None)

        fh2 = StringIO(self.config2)
        with self.assertRaises(NoOptionError):
            make_study_from_cmd('test@test.com', 'newstudy2', fh2)


@qiita_test_checker()
class SampleTemplateAdderTests(TestCase):
    """"""

    def setUp(self):
        """"""
        # Create a sample template file
        self.samp_temp_path = join(dirname(__file__), 'test_data',
                                   'sample_template.txt')

        # create a new study to attach the sample template
        info = {
            "timeseries_type_id": 1,
            "metadata_complete": True,
            "mixs_compliant": True,
            "number_samples_collected": 4,
            "number_samples_promised": 4,
            "portal_type_id": 3,
            "study_alias": "TestStudy",
            "study_description": "Description of a test study",
            "study_abstract": "No abstract right now...",
            "emp_person_id": StudyPerson(2),
            "principal_investigator_id": StudyPerson(3),
            "lab_person_id": StudyPerson(1)
        }
        self.study = Study.create(User('test@foo.bar'),
                                  "Test study", [1], info)

    def test_sample_template_adder(self):
        """Correctly adds a sample template to the DB"""
        st = sample_template_adder(self.samp_temp_path, self.study.id)
        self.assertEqual(st.id, self.study.id)


CONFIG_1 = """[required]
timeseries_type_id = 1
metadata_complete = True
mixs_compliant = True
number_samples_collected = 50
number_samples_promised = 25
portal_type_id = 3
principal_investigator = SomeDude, somedude@foo.bar
reprocess = False
study_alias = 'test study'
study_description = 'test study description'
study_abstract = 'study abstract'
efo_ids = 1,2,3,4
[optional]
lab_person = SomeDude, somedude@foo.bar
funding = 'funding source'
vamps_id = vamps_id
"""

CONFIG_2 = """[required]
timeseries_type_id = 1
metadata_complete = True
number_samples_collected = 50
number_samples_promised = 25
portal_type_id = 3
principal_investigator = SomeDude, somedude@foo.bar
reprocess = False
study_alias = 'test study'
study_description = 'test study description'
study_abstract = 'study abstract'
efo_ids = 1,2,3,4
[optional]
lab_person = SomeDude, somedude@foo.bar
funding = 'funding source'
vamps_id = vamps_id
"""

if __name__ == "__main__":
    main()
