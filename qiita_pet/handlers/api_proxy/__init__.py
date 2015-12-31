# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

__version__ = "0.2.0-dev"
from .sample_template import (
    sample_template_post_req, sample_template_put_req,
    sample_template_summary_get_req, sample_template_delete_req,
    sample_template_filepaths_get_req, sample_template_get_req)
from .prep_template import (
    prep_template_summary_get_req, prep_template_post_req,
    prep_template_put_req, prep_template_delete_req, prep_template_get_req,
    prep_template_graph_get_req, prep_template_filepaths_get_req)
from .studies import (
    data_types_get_req, study_get_req, study_prep_get_req, study_delete_req)
from .artifact import (artifact_graph_get_req, artifact_get_req,
                       artifact_status_put_req, artifact_delete_req)

__all__ = ['prep_template_summary_get_req', 'sample_template_post_req',
           'sample_template_put_req', 'data_types_get_req',
           'study_get_req', 'sample_template_summary_get_req',
           'sample_template_delete_req', 'sample_template_filepaths_get_req',
           'prep_template_summary_get_req', 'prep_template_post_req',
           'prep_template_put_req', 'prep_template_delete_req',
           'prep_template_graph_get_req', 'prep_template_filepaths_get_req',
           'artifact_graph_get_req', 'prep_template_get_req',
           'study_delete_req', 'study_prep_get_req', 'sample_template_get_req',
           'artifact_get_req', 'artifact_status_put_req',
           'artifact_delete_req']
