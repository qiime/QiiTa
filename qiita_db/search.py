r"""
Search objects (:mod: `qiita_db.search`)
====================================

..currentmodule:: qiita_db.search

This module provides functionality for searching studies and samples contained
in the qiita database. All language processing and querying of the database is
contained within each object.

Classes
-------

..autosummary::
    :toctree: generated/

    QiitaStudySearch

Examples
--------
Searches are done using boolean language, with AND, OR, and NOT supported,
as well as ordering through parenthesis. You can search over metadata using the
following operators::

>  <  =  <=  >=  includes

The operators act as they normally do, with includes used for substring
searches.

The object itself is used to search using the call method. In this
example, we will use the complex query::

(sample_type = ENVO:soil AND COMMON_NAME = "rhizosphere metagenome") AND
NOT Description_duplicate includes Burmese

>>> from qiita_db.search import QiitaStudySearch # doctest: +SKIP
>>> search = QiitaStudySearch() # doctest: +SKIP
>>> res, meta = search('(sample_type = ENVO:soil AND COMMON_NAME = '
...                    '"rhizosphere metagenome") AND NOT '
...                    'Description_duplicate includes Burmese',
...                    "test@foo.bar") # doctest: +SKIP
>>> print(res) # doctest: +SKIP
{1: [['SKM4.640180', 'rhizosphere metagenome', 'Bucu Rhizo', 'ENVO:soil'],
     ['SKM5.640177', 'rhizosphere metagenome', 'Bucu Rhizo', 'ENVO:soil'],
     ['SKD4.640185', 'rhizosphere metagenome', 'Diesel Rhizo', 'ENVO:soil'],
     ['SKD6.640190', 'rhizosphere metagenome', 'Diesel Rhizo', 'ENVO:soil'],
     ['SKM6.640187', 'rhizosphere metagenome', 'Bucu Rhizo', 'ENVO:soil'],
     ['SKD5.640186', 'rhizosphere metagenome', 'Diesel Rhizo', 'ENVO:soil']]}
>>> print(meta) # doctest: +SKIP
["COMMON_NAME", "Description_duplicate", "sample_type"]

Note that the userid performing the search must also be passed, so the search
knows what studies are accessable. Also note that the sample list is in the
order of sample ID followed by metadata in the same order as the metadata
headers returned.
"""

# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from pyparsing import (alphas, nums, Word, dblQuotedString, oneOf, Optional,
                       opAssoc, CaselessLiteral, removeQuotes, Group,
                       operatorPrecedence, stringEnd)

from qiita_db.util import scrub_data, typecast_string, get_table_cols
from qiita_db.sql_connection import SQLConnectionHandler
from qiita_db.study import Study
from qiita_db.exceptions import QiitaDBIncompatibleDatatypeError


# classes to be constructed at parse time, from intermediate ParseResults
class UnaryOperation(object):
    def __init__(self, t):
        self.op, self.a = t[0]


class BinaryOperation(object):
    def __init__(self, t):
        self.op = t[0][1]
        self.operands = t[0][0::2]


class SearchAnd(BinaryOperation):
    def generate_sql(self):
        return "(%s)" % " AND ".join(oper.generate_sql()
                                     for oper in self.operands)

    def __repr__(self):
        return "AND:(%s)" % (",".join(str(oper) for oper in self.operands))


class SearchOr(BinaryOperation):
    def generate_sql(self):
        return "(%s)" % " OR ".join(oper.generate_sql()
                                    for oper in self.operands)

    def __repr__(self):
        return "OR:(%s)" % (",".join(str(oper) for oper in self.operands))


class SearchNot(UnaryOperation):
    def generate_sql(self):
        return "NOT %s" % self.a.generate_sql()

    def __repr__(self):
        return "NOT:(%s)" % str(self.a)


class SearchTerm(object):
    # column names from required_sample_info table
    required_cols = set(get_table_cols("required_sample_info"))
    # column names from study table
    study_cols = set(get_table_cols("study"))

    def __init__(self, tokens):
        self.term = tokens[0]
        # clean all the inputs
        for pos, term in enumerate(self.term):
            self.term[pos] = scrub_data(term)

    def generate_sql(self):
        # we can assume that the metadata is either in required_sample_info
        # or the study-specific table
        column_name, operator, argument = self.term
        argument_type = type(typecast_string(argument))

        allowable_types = {int: {'<', '<=', '=', '>=', '>'},
                           float: {'<', '<=', '=', '>=', '>'},
                           str: {'=', 'includes', 'startswith'}}

        if operator not in allowable_types[argument_type]:
            raise QiitaDBIncompatibleDatatypeError(operator, argument_type)

        if column_name in self.required_cols:
            column_name = "r.%s" % column_name.lower()
        elif column_name in self.study_cols:
            column_name = "st.%s" % column_name.lower()
        else:
            column_name = "sa.%s" % column_name.lower()

        if operator == "includes":
            # substring search, so create proper query for it
            return "LOWER(%s) LIKE '%%%s%%'" % (column_name, argument.lower())
        else:
            # standard query so just return it, adding quotes if string
            if argument_type == str:
                argument = ''.join(("'", argument, "'"))
            return ' '.join([column_name, operator, argument])

    def __repr__(self):
        column_name, operator, argument = self.term
        if operator == "includes":
            return "LOWER(%s) LIKE '%%%s%%')" % (column_name, argument.lower())
        else:
            return ' '.join(self.term)


class QiitaStudySearch(object):
    """QiitaStudySearch object to parse and run searches on studies."""

    # column names from required_sample_info table
    required_cols = set(get_table_cols("required_sample_info"))
    # column names from study table
    study_cols = set(get_table_cols("study"))

    def __call__(self, searchstr, user):
        """Runs a Study query and returns matching studies and samples

        Parameters
        ----------
        searchstr : str
            Search string to use
        user : User object
            User making the search. Needed for permissions checks.

        Returns
        -------
        dict
            Found samples in format
            {study_id: [[samp_id1, meta1, meta2, ...],
                        [samp_id2, meta1, meta2, ...], ...}
        list
            metadata column names searched for

        Notes
        -----
        Metadata information for each sample is in the same order as the
        metadata columns list returned

        Metadata column names and string searches are case-sensitive
        """
        study_sql, sample_sql, meta_headers = \
            self._parse_study_search_string(searchstr, True)
        conn_handler = SQLConnectionHandler()
        # get all studies containing the metadata headers requested
        study_ids = {x[0] for x in conn_handler.execute_fetchall(study_sql)}
        # strip to only studies user has access to
        if user.level not in {'admin', 'dev', 'superuser'}:
            study_ids = study_ids.intersection(Study.get_by_status('public') +
                                               user.user_studies +
                                               user.shared_studies)

        results = {}
        # run search on each study to get out the matching samples
        for sid in study_ids:
            study_res = conn_handler.execute_fetchall(sample_sql.format(sid))
            if study_res:
                # only add study to results if actually has samples in results
                results[sid] = study_res
        return results, meta_headers

    def _parse_study_search_string(self, searchstr,
                                   only_with_processed_data=False):
        """parses string into SQL query for study search

        Parameters
        ----------
        searchstr : str
            The string to parse
        only_with_processed_data : bool
            Whether or not to return studies with processed data.

        Returns
        -------
        study_sql : str
            SQL query for selecting studies with the required metadata columns
        sample_sql : str
            SQL query for each study to get the sample ids that mach the query
        meta_headers : list
            metadata categories in the query string in alphabetical order

        Notes
        -----
        All searches are case-sensitive

        References
        ----------
        .. [1] McGuire P (2007) Getting started with pyparsing.
        """
        # build the parse grammar
        category = Word(alphas + nums + "_")
        seperator = oneOf("> < = >= <= !=") | CaselessLiteral("includes") | \
            CaselessLiteral("startswith")
        value = Word(alphas + nums + "_" + ":" + ".") | \
            dblQuotedString().setParseAction(removeQuotes)
        criterion = Group(category + seperator + value)
        criterion.setParseAction(SearchTerm)
        and_ = CaselessLiteral("and")
        or_ = CaselessLiteral("or")
        not_ = CaselessLiteral("not")
        optional_seps = Optional(and_ | or_ | not_)

        # create the grammar for parsing operators AND, OR, NOT
        search_expr = operatorPrecedence(
            criterion, [
                (not_, 1, opAssoc.RIGHT, SearchNot),
                (and_, 2, opAssoc.LEFT, SearchAnd),
                (or_, 2, opAssoc.LEFT, SearchOr)])

        # parse the search string to get out the SQL WHERE formatted query
        eval_stack = (search_expr + stringEnd).parseString(searchstr)[0]
        sql_where = eval_stack.generate_sql()

        # this lookup will be used to select only studies with columns
        # of the correct type
        type_lookup = {int: 'integer', float: 'float8', str: 'varchar'}

        # parse out all metadata headers we need to have in a study, and
        # their corresponding types
        all_headers = [c[0][0].term[0] for c in
                       (criterion + optional_seps).scanString(searchstr)]
        meta_headers = set(all_headers)
        all_types = [c[0][0].term[2] for c in
                     (criterion + optional_seps).scanString(searchstr)]
        all_types = [type_lookup[type(typecast_string(s))] for s in all_types]

        # sort headers and types so they return in same order every time.
        # Should be a relatively short list so very quick
        # argsort implementation taken from
        # http://stackoverflow.com/questions/3382352/
        # equivalent-of-numpy-argsort-in-basic-python
        sort_order = sorted(range(len(all_headers)),
                            key=all_headers.__getitem__)
        all_types = [all_types[x] for x in sort_order]
        all_headers.sort()

        # At this point it is possible that a metadata header has been
        # reference more than once in the query. If the types agree, then we
        # do not need to do anything. If the types do not agree (specifically,
        # if it appears to be numerical in one case and string in another),
        # then we need to give varchar the precedence.
        meta_header_type_lookup = dict()
        for header, header_type in zip(all_headers, all_types):
            if header not in meta_header_type_lookup:
                meta_header_type_lookup[header] = header_type
            else:
                if header_type == 'varchar' or \
                        meta_header_type_lookup[header] == 'varchar':
                    meta_header_type_lookup[header] = 'varchar'

        # create the study finding SQL
        # remove metadata headers that are in required_sample_info table
        meta_headers = meta_headers.difference(self.required_cols).difference(
            self.study_cols)

        # get all study ids that contain all metadata categories searched for
        sql = []
        if meta_headers:
            # have study-specific metadata, so need to find specific studies
            for meta in meta_headers:
                if meta_header_type_lookup[meta] in ('integer', 'float8'):
                    allowable_types = "('integer', 'float8')"
                else:
                    allowable_types = "('varchar')"

                sql.append("SELECT study_id FROM qiita.study_sample_columns "
                           "WHERE lower(column_name) = lower('%s') and "
                           "column_type in %s" %
                           (scrub_data(meta), allowable_types))
        else:
            # no study-specific metadata, so need all studies
            sql.append("SELECT study_id FROM qiita.study_sample_columns")

        # combine the query
        if only_with_processed_data:
            sql.append('SELECT study_id FROM qiita.study_processed_data')
        study_sql = ' INTERSECT '.join(sql)

        # create  the sample finding SQL, getting both sample id and values
        # build the sql formatted list of metadata headers
        header_info = []
        for meta in meta_header_type_lookup:
            if meta in self.required_cols:
                header_info.append("r.%s" % meta)
            elif meta in self.study_cols:
                header_info.append("st.%s" % meta)
            else:
                header_info.append("sa.%s" % meta)
        # build the SQL query
        sample_sql = ("SELECT r.sample_id,%s FROM qiita.required_sample_info "
                      "r JOIN qiita.sample_{0} sa ON sa.sample_id = "
                      "r.sample_id JOIN qiita.study st ON st.study_id = "
                      "r.study_id WHERE %s" %
                      (','.join(header_info), sql_where))
        return study_sql, sample_sql, meta_header_type_lookup.keys()
