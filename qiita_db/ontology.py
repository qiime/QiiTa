# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

r"""
Ontology and Controlled Vocabulary objects (:mod:`qiita_db.study`)
==================================================================

.. currentmodule:: qiita_db.ontology

This module provides the encapsulation of an ontology. The resulting object can
be used to interrogate the terms in an ontology.

Classes
-------

.. autosummary::
   :toctree: generated/

   Ontology
"""

from __future__ import division

from .base import QiitaObject
from .util import convert_from_id
from .sql_connection import SQLConnectionHandler


class Ontology(QiitaObject):
    """Object to access ontologies and associated terms from the database

    Attributes
    ----------
    terms
    shortname
    """
    _table = 'ontology'

    def __contains__(self, value):
        conn_handler = SQLConnectionHandler()
        sql = """SELECT EXISTS (SELECT * FROM qiita.term t JOIN qiita.{0} o
                 on t.ontology_id = o.ontology_id WHERE o.ontology_id = %s and
                 term = %s)""".format(self._table)

        return conn_handler.execute_fetchone(sql, (self._id, value))[0]

    @property
    def terms(self):
        conn_handler = SQLConnectionHandler()
        sql = """SELECT term FROM qiita.term WHERE ontology_id = %s"""

        return [row[0] for row in
                conn_handler.execute_fetchall(sql, [self.id])]

    @property
    def shortname(self):
        return convert_from_id(self.id, 'ontology')
