# Feberuary 7, 2015
# This patch recreates all the QIIME mapping files to avoid lower/upper case
# problems. See https://github.com/biocore/qiita/issues/799
#
# heavily based on 7.py

from os.path import basename

from skbio.util import flatten

from qiita_db.sql_connection import Transaction
from qiita_db.metadata_template import PrepTemplate

trans = Transaction('unlink-bad-mapping-files')

sql = "SELECT prep_template_id FROM qiita.prep_template"
trans.add(sql)
all_ids = trans.execute(commit=False)[0]

# remove all the bad mapping files
for prep_template_id in all_ids:

    prep_template_id = prep_template_id[0]
    pt = PrepTemplate(prep_template_id)
    fps = pt.get_filepaths()

    # get the QIIME mapping file, note that the way to figure out what is and
    # what's not a qiime mapping file is to check for the existance of the
    # word qiime in the basename of the file path, hacky but that's the way
    # it is being done in qiita_pet/uimodules/raw_data_tab.py
    mapping_files = [f for f in fps if '_qiime_' in basename(f[1])]

    table = 'prep_template_filepath'
    column = 'prep_template_id'

    # unlink all the qiime mapping files for this prep template object
    for mf in mapping_files:

        # (1) get the ids that we are going to delete.
        # because of the FK restriction, we cannot just delete the ids
        trans.add(
            'SELECT filepath_id FROM qiita.{0} WHERE '
            '{1}=%s and filepath_id=%s'.format(table, column), (pt.id, mf[0]))
        ids = trans.execute(commit=False)[-1]
        ids = flatten(ids)

        # (2) delete the entries from the prep_template_filepath table
        trans.add(
            "DELETE FROM qiita.{0} "
            "WHERE {1}=%s and filepath_id=%s;".format(table, column),
            (pt.id, mf[0]))

        # (3) delete the entries from the filepath table
        trans.add(
            "DELETE FROM qiita.filepath WHERE "
            "filepath_id IN ({0});".format(', '.join(map(str, ids))))

trans.execute()

# create correct versions of the mapping files
for prep_template_id in all_ids:

    prep_template_id = prep_template_id[0]
    pt = PrepTemplate(prep_template_id)

    # we can guarantee that all the filepaths will be prep templates so
    # we can just generate the qiime mapping files
    for _, fpt in pt.get_filepaths():
        pt.create_qiime_mapping_file(fpt)
