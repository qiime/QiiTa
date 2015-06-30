from unittest import TestCase, main

from qiita_core.util import qiita_test_checker
from qiita_db.portal import (
    add_studies_to_portal, remove_studies_from_portal, get_studies_by_portal,
    add_analyses_to_portal, remove_analyses_from_portal,
    get_analyses_by_portal, _check_analyses, _check_studies, create_portal,
    remove_portal)
from qiita_db.study import Study
from qiita_db.analysis import Analysis
from qiita_db.exceptions import QiitaDBError, QiitaDBDuplicateError
from qiita_core.qiita_settings import qiita_config

# Only test if functions available
if qiita_config.portal == "QIITA":
    @qiita_test_checker()
    class TestPortal(TestCase):
        def setUp(self):
            self.study = Study(1)
            self.analysis = Analysis(1)

        def tearDown(self):
            qiita_config.portal = 'QIITA'

        def test_add_portal(self):
            create_portal("NEWPORTAL", "SOMEDESC")
            obs = self.conn_handler.execute_fetchall(
                "SELECT * FROM qiita.portal_type")
            exp = [[1, 'QIITA', 'QIITA portal. Access to all data stored '
                    'in database.'],
                   [2, 'EMP', 'EMP portal'],
                   [4, 'NEWPORTAL', 'SOMEDESC']]

            self.assertItemsEqual(obs, exp)

            with self.assertRaises(QiitaDBDuplicateError):
                create_portal("EMP", "DOESNTMATTERFORDESC")

        def test_remove_portal(self):
            create_portal("NEWPORTAL", "SOMEDESC")
            remove_portal("NEWPORTAL")
            obs = self.conn_handler.execute_fetchall(
                "SELECT * FROM qiita.portal_type")
            exp = [[1, 'QIITA', 'QIITA portal. Access to all data stored '
                    'in database.'],
                   [2, 'EMP', 'EMP portal']]
            self.assertItemsEqual(obs, exp)

            with self.assertRaises(QiitaDBError):
                remove_portal("QIITA")

        def test_check_studies(self):
            with self.assertRaises(QiitaDBError):
                _check_studies([2000000000000, 122222222222222])

        def test_check_analyses(self):
            with self.assertRaises(QiitaDBError):
                _check_analyses([2000000000000, 122222222222222])

            with self.assertRaises(QiitaDBError):
                _check_analyses([8, 9])

        def test_get_studies_by_portal(self):
            obs = get_studies_by_portal('EMP')
            self.assertEqual(obs, set())

            obs = get_studies_by_portal('QIITA')
            self.assertEqual(obs, {1})

        def test_add_study_portals(self):
            add_studies_to_portal('EMP', [self.study.id])
            obs = self.study._portals
            self.assertEqual(obs, ['EMP', 'QIITA'])

        def test_remove_study_portals(self):
            with self.assertRaises(ValueError):
                remove_studies_from_portal('QIITA', [self.study.id])

            add_studies_to_portal('EMP', [self.study.id])
            remove_studies_from_portal('EMP', [self.study.id])
            obs = self.study._portals
            self.assertEqual(obs, ['QIITA'])

        def test_get_analyses_by_portal(self):
            obs = get_analyses_by_portal('EMP')
            self.assertEqual(obs, set())

            obs = get_analyses_by_portal('QIITA')
            self.assertEqual(obs, set(x for x in range(1, 11)))

        def test_add_analysis_portals(self):
            add_analyses_to_portal('EMP', [self.analysis.id])
            obs = self.analysis._portals
            self.assertEqual(obs, ['EMP', 'QIITA'])

        def test_remove_analysis_portals(self):
            with self.assertRaises(ValueError):
                remove_analyses_from_portal('QIITA', [self.analysis.id])

            add_analyses_to_portal('EMP', [self.analysis.id])
            remove_analyses_from_portal('EMP', [self.analysis.id])
            obs = self.analysis._portals
            self.assertEqual(obs, ['QIITA'])


if __name__ == '__main__':
    main()
