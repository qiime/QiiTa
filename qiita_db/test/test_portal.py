from unittest import TestCase, main

from qiita_core.util import qiita_test_checker
from qiita_core.exceptions import IncompetentQiitaDeveloperError
from qiita_db.portal import Portal
from qiita_db.study import Study
from qiita_db.analysis import Analysis
from qiita_db.exceptions import QiitaDBError, QiitaDBDuplicateError
from qiita_core.qiita_settings import qiita_config


@qiita_test_checker()
class TestPortal(TestCase):
    def setUp(self):
        self.study = Study(1)
        self.analysis = Analysis(1)
        self.qiita_portal = Portal('QIITA')
        self.emp_portal = Portal('EMP')

    def tearDown(self):
        qiita_config.portal = 'QIITA'

    def test_add_portal(self):
        Portal.create("NEWPORTAL", "SOMEDESC")
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.portal_type")
        exp = [[1, 'QIITA', 'QIITA portal. Access to all data stored '
                'in database.'],
               [2, 'EMP', 'EMP portal'],
               [4, 'NEWPORTAL', 'SOMEDESC']]
        self.assertItemsEqual(obs, exp)

        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.analysis_portal")
        exp = [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 1], [8, 1],
               [9, 1], [10, 1], [11, 4], [12, 4], [13, 4], [14, 4]]
        self.assertEqual(obs, exp)

        with self.assertRaises(QiitaDBDuplicateError):
            Portal.create("EMP", "DOESNTMATTERFORDESC")

    def test_remove_portal(self):
        Portal.create("NEWPORTAL", "SOMEDESC")
        Portal.delete("NEWPORTAL")
        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.portal_type")
        exp = [[1, 'QIITA', 'QIITA portal. Access to all data stored '
                'in database.'],
               [2, 'EMP', 'EMP portal']]
        self.assertItemsEqual(obs, exp)

        obs = self.conn_handler.execute_fetchall(
            "SELECT * FROM qiita.analysis_portal")
        exp = [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 1], [8, 1],
               [9, 1], [10, 1]]
        self.assertEqual(obs, exp)

        with self.assertRaises(IncompetentQiitaDeveloperError):
            Portal.delete("NOEXISTPORTAL")
        with self.assertRaises(QiitaDBError):
            Portal.delete("QIITA")

    def test_check_studies(self):
        with self.assertRaises(QiitaDBError):
            self.qiita_portal._check_studies([2000000000000, 122222222222222])

    def test_check_analyses(self):
        with self.assertRaises(QiitaDBError):
            self.qiita_portal._check_analyses([2000000000000, 122222222222222])

        with self.assertRaises(QiitaDBError):
            self.qiita_portal._check_analyses([8, 9])

    def test_get_studies_by_portal(self):
        obs = self.emp_portal.get_studies()
        self.assertEqual(obs, set())

        obs = self.qiita_portal.get_studies()
        self.assertEqual(obs, {1})

    def test_add_study_portals(self):
        self.emp_portal.add_studies([self.study.id])
        obs = self.study._portals
        self.assertEqual(obs, ['EMP', 'QIITA'])

    def test_remove_study_portals(self):
        with self.assertRaises(ValueError):
            self.qiita_portal.remove_studies([self.study.id])

        self.emp_portal.add_studies([self.study.id])
        self.emp_portal.remove_studies([self.study.id])
        obs = self.study._portals
        self.assertEqual(obs, ['QIITA'])

    def test_get_analyses_by_portal(self):
        obs = self.emp_portal.get_analyses()
        self.assertEqual(obs, set())

        obs = self.qiita_portal.get_analyses()
        self.assertEqual(obs, set(x for x in range(1, 11)))

    def test_add_analysis_portals(self):
        self.emp_portal.add_analyses([self.analysis.id])
        obs = self.analysis._portals
        self.assertEqual(obs, ['EMP', 'QIITA'])

    def test_remove_analysis_portals(self):
        with self.assertRaises(ValueError):
            self.qiita_portal.remove_analyses([self.analysis.id])

        self.emp_portal.add_analyses([self.analysis.id])
        self.emp_portal.remove_analyses([self.analysis.id])
        obs = self.analysis._portals
        self.assertEqual(obs, ['QIITA'])


if __name__ == '__main__':
    main()
