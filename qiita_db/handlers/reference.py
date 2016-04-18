# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from tornado.web import HTTPError

from .oauth2 import OauthBaseHandler, authenticate_oauth
import qiita_db as qdb


def _get_reference(r_id):
    """Returns the reference with the given id if exists

    Parameters
    ----------
    r_id : int
        The reference id

    Returns
    -------
    qiita_db.reference.Reference
        The requested reference

    Raises
    ------
    HTTPError
        If the reference does not exist, with error code 404
        If there is a problem instantiating the reference, with error code 500
    """
    try:
        reference = qdb.reference.Reference(r_id)
    except qdb.exceptions.QiitaDBUnknownIDError:
        raise HTTPError(404)
    except Exception as e:
        raise HTTPError(500, 'Error instantiating the reference: %s' % str(e))

    return reference


class ReferenceFilepathsHandler(OauthBaseHandler):
    @authenticate_oauth
    def get(self, reference_id):
        """Retrieves the filepath information of the given reference

        Parameters
        ----------
        reference_id : str
            The id of the reference whose filepath information is being
            retrieved

        Returns
        -------
        dict
            {'filepaths': list of (str, str)}
            The filepaths attached to the reference and their filepath types
        """
        with qdb.sql_connection.TRN:
            reference = _get_reference(reference_id)

            fps = [(reference.sequence_fp, "reference_seqs")]
            tax_fp = reference.taxonomy_fp
            if tax_fp:
                fps.append((tax_fp, "reference_tax"))
            tree_fp = reference.tree_fp
            if tree_fp:
                fps.append((tree_fp, "reference_tree"))

            response = {'filepaths': fps}

        self.write(response)
