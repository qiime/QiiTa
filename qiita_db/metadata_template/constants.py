# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from collections import namedtuple
from future.utils import viewkeys, viewvalues

Restriction = namedtuple('Restriction', ['columns', 'error_msg'])

# A dict containing the restrictions that apply to the sample templates
SAMPLE_TEMPLATE_COLUMNS = {
    # The following columns are required by EBI for submission
    'EBI': Restriction(columns={'collection_timestamp': 'timestamp',
                                'physical_specimen_location': 'varchar',
                                'taxon_id': 'integer',
                                'scientific_name': 'varchar'},
                       error_msg="EBI submission disabled"),
    # The following columns are required for the official main QIITA site
    'qiita_main': Restriction(columns={'sample_type': 'varchar',
                                       'description': 'varchar',
                                       'physical_specimen_remaining': 'bool',
                                       'dna_extracted': 'bool',
                                       'latitude': 'float8',
                                       'longitude': 'float8',
                                       'host_subject_id': 'varchar'},
                              error_msg="Processed data approval disabled")
}

# A dict containing the restrictions that apply to the prep templates
PREP_TEMPLATE_COLUMNS = {
    # The following columns are required by EBI for submission
    'EBI': Restriction(
        columns={'primer': 'varchar',
                 'center_name': 'varchar',
                 'platform': 'varchar',
                 'library_construction_protocol': 'varchar',
                 'experiment_design_description': 'varchar'},
        error_msg="EBI submission disabled")
}

# Different prep templates have different requirements depending on the data
# type. We create a dictionary for each of these special datatypes

TARGET_GENE_DATA_TYPES = ['16S', '18S', 'ITS']

PREP_TEMPLATE_COLUMNS_TARGET_GENE = {
    # The following columns are required by QIIME to execute split libraries
    'demultiplex': Restriction(
        columns={'barcode': 'varchar',
                 'primer': 'varchar'},
        error_msg="Demultiplexing disabled. You will not be able to "
                  "preprocess your raw data"),
    # The following columns are required by Qiita to know how to execute split
    # libraries using QIIME over a study with multiple illumina lanes
    'demultiplex_multiple': Restriction(
        columns={'barcode': 'varchar',
                 'primer': 'varchar',
                 'run_prefix': 'varchar'},
        error_msg="Demultiplexing with multiple input files disabled. If your "
                  "raw data includes multiple raw input files, you will not "
                  "be able to preprocess your raw data")
}

# This list is useful to have if we want to loop through all the restrictions
# in a template-independent manner
ALL_RESTRICTIONS = [SAMPLE_TEMPLATE_COLUMNS, PREP_TEMPLATE_COLUMNS,
                    PREP_TEMPLATE_COLUMNS_TARGET_GENE]


# A set holding all the controlled columns, useful to avoid recalculating it
def _col_iterator():
    for r_set in ALL_RESTRICTIONS:
        for restriction in viewvalues(r_set):
            for cols in viewkeys(restriction.columns):
                yield cols

CONTROLLED_COLS = set(col for col in _col_iterator())
