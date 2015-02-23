# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from dateutil.parser import parse
from os import listdir, remove
from os.path import join, exists
from functools import partial
from future import standard_library
from future.utils import viewitems
from collections import defaultdict
from shutil import move

from .study import Study, StudyPerson
from .user import User
from .util import (get_filetypes, get_filepath_types, compute_checksum,
                   convert_to_id)
from .data import RawData, PreprocessedData, ProcessedData
from .metadata_template import (SampleTemplate, PrepTemplate,
                                load_template_to_dataframe)
from .parameters import (PreprocessedIlluminaParams, Preprocessed454Params,
                         ProcessedSortmernaParams)
from .sql_connection import SQLConnectionHandler

with standard_library.hooks():
    from configparser import ConfigParser


SUPPORTED_PARAMS = ['preprocessed_sequence_illumina_params',
                    'preprocessed_sequence_454_params',
                    'processed_params_sortmerna']


def load_study_from_cmd(owner, title, info):
    r"""Adds a study to the database

    Parameters
    ----------
    owner : str
        The email address of the owner of the study_abstract
    title : str
        The title of the study_abstract
    info : file-like object
        File-like object containing study information

    """
    # Parse the configuration file
    config = ConfigParser()
    config.readfp(info)

    optional = dict(config.items('optional'))

    def get_optional(name):
        return optional.get(name, None)

    get_required = partial(config.get, 'required')
    required_fields = ['timeseries_type_id', 'mixs_compliant',
                       'portal_type_id', 'reprocess', 'study_alias',
                       'study_description', 'study_abstract',
                       'metadata_complete', 'efo_ids',
                       'principal_investigator']
    optional_fields = ['funding', 'most_recent_contact', 'spatial_series',
                       'number_samples_collected', 'number_samples_promised',
                       'vamps_id', 'study_id']
    infodict = {}
    for value in required_fields:
        infodict[value] = get_required(value)

    # this will eventually change to using the Experimental Factory Ontolgoy
    # names
    efo_ids = infodict.pop('efo_ids')
    efo_ids = [x.strip() for x in efo_ids.split(',')]

    for value in optional_fields:
        optvalue = get_optional(value)
        if optvalue is not None:
            infodict[value] = optvalue

    emp_person_name_email = get_optional('emp_person_name')
    if emp_person_name_email is not None:
        emp_name, emp_email, emp_affiliation = emp_person_name_email.split(',')
        infodict['emp_person_id'] = StudyPerson.create(emp_name.strip(),
                                                       emp_email.strip(),
                                                       emp_affiliation.strip())
    lab_name_email = get_optional('lab_person')
    if lab_name_email is not None:
        lab_name, lab_email, lab_affiliation = lab_name_email.split(',')
        infodict['lab_person_id'] = StudyPerson.create(lab_name.strip(),
                                                       lab_email.strip(),
                                                       lab_affiliation.strip())

    pi_name_email = infodict.pop('principal_investigator')
    pi_name, pi_email, pi_affiliation = pi_name_email.split(',', 2)
    infodict['principal_investigator_id'] = StudyPerson.create(
        pi_name.strip(), pi_email.strip(), pi_affiliation.strip())

    return Study.create(User(owner), title, efo_ids, infodict)


def load_preprocessed_data_from_cmd(study_id, params_table, filedir,
                                    filepathtype, params_id,
                                    submitted_to_insdc_status,
                                    prep_template_id, data_type):
    r"""Adds preprocessed data to the database

    Parameters
    ----------
    study_id : int
        The study id to which the preprocessed data belongs
    filedir : str
        Directory path of the preprocessed data
    filepathtype: str
        The filepath_type of the preprecessed data
    params_table_name : str
        The name of the table which contains the parameters of the
        preprocessing
    params_id : int
        The id of parameters int the params_table
    submitted_to_insdc_status : str, {'not submitted', 'submitting', \
            'success', 'failed'}
        INSDC submission status
    prep_template_id : int
        Prep template id associated with data
    data_type : str
        The data type of the template
    """
    fp_types_dict = get_filepath_types()
    fp_type = fp_types_dict[filepathtype]
    filepaths = [(join(filedir, fp), fp_type) for fp in listdir(filedir)]
    pt = None if prep_template_id is None else PrepTemplate(prep_template_id)
    return PreprocessedData.create(
        Study(study_id), params_table, params_id, filepaths, prep_template=pt,
        submitted_to_insdc_status=submitted_to_insdc_status,
        data_type=data_type)


def load_sample_template_from_cmd(sample_temp_path, study_id):
    r"""Adds a sample template to the database

    Parameters
    ----------
    sample_temp_path : str
        Path to the sample template file
    study_id : int
        The study id to which the sample template belongs
    """
    sample_temp = load_template_to_dataframe(sample_temp_path)

    return SampleTemplate.create(sample_temp, Study(study_id))


def load_prep_template_from_cmd(prep_temp_path, raw_data_id, study_id,
                                data_type):
    r"""Adds a prep template to the database

    Parameters
    ----------
    prep_temp_path : str
        Path to the prep template file
    raw_data_id : int
        The raw data id to which the prep template belongs
    study_id : int
        The study id to which the prep template belongs
    data_type : str
        The data type of the prep template
    """
    prep_temp = load_template_to_dataframe(prep_temp_path)
    return PrepTemplate.create(prep_temp, RawData(raw_data_id),
                               Study(study_id), data_type)


def load_raw_data_cmd(filepaths, filepath_types, filetype, study_ids):
    """Add new raw data by populating the relevant tables

    Parameters
    ----------
    filepaths : iterable of str
        Paths to the raw data files
    filepath_types : iterable of str
        Describes the contents of the files.
    filetype : str
        The type of file being loaded
    study_ids : iterable of int
        The IDs of the studies with which to associate this raw data

    Returns
    -------
    qiita_db.RawData
        The newly created `qiita_db.RawData` object
    """
    if len(filepaths) != len(filepath_types):
        raise ValueError("Please pass exactly one filepath_type for each "
                         "and every filepath")

    filetypes_dict = get_filetypes()
    filetype_id = filetypes_dict[filetype]

    filepath_types_dict = get_filepath_types()
    filepath_types = [filepath_types_dict[x] for x in filepath_types]

    studies = [Study(x) for x in study_ids]

    return RawData.create(filetype_id, studies,
                          filepaths=list(zip(filepaths, filepath_types)))


def load_processed_data_cmd(fps, fp_types, processed_params_table_name,
                            processed_params_id, preprocessed_data_id=None,
                            study_id=None, processed_date=None):
    """Add a new processed data entry

    Parameters
    ----------
    fps : list of str
        Paths to the processed data files to associate with the ProcessedData
        object
    fp_types: list of str
        The types of files, one per fp
    processed_params_table_name : str
        The name of the processed_params_ table to use
    processed_params_id : int
        The ID of the row in the processed_params_ table
    preprocessed_data_id : int, optional
        Defaults to ``None``. The ID of the row in the preprocessed_data table.
    processed_date : str, optional
        Defaults to ``None``. The date and time to use as the processing date.
        Must be interpretable as a datetime object

    Returns
    -------
    qiita_db.ProcessedData
        The newly created `qiita_db.ProcessedData` object
    """
    if len(fps) != len(fp_types):
        raise ValueError("Please pass exactly one fp_type for each "
                         "and every fp")

    fp_types_dict = get_filepath_types()
    fp_types = [fp_types_dict[x] for x in fp_types]

    if preprocessed_data_id is not None:
        preprocessed_data = PreprocessedData(preprocessed_data_id)
    else:
        preprocessed_data = None

    if study_id is not None:
        study = Study(study_id)
    else:
        study = None

    if processed_date is not None:
        processed_date = parse(processed_date)

    return ProcessedData.create(processed_params_table_name,
                                processed_params_id, list(zip(fps, fp_types)),
                                preprocessed_data, study, processed_date)


def load_parameters_from_cmd(name, fp, table):
    """Add a new parameters entry on `table`

    Parameters
    ----------
    fp : str
        The filepath to the parameters file
    table : str
        The name of the table to add the parameters

    Returns
    -------
    qiita_db.BaseParameters
        The newly `qiita_db.BaseParameters` object

    Raises
    ------
    ValueError
        If the table does not exists on the DB
        If the fp is not correctly formatted

    Notes
    -----
    `fp` should be a tab-delimited text file following this format:
        parameter_1<TAB>value
        parameter_2<TAB>value
        ...
    """
    if table not in SUPPORTED_PARAMS:
        raise ValueError("Table %s not supported. Choose from: %s"
                         % (table, ', '.join(SUPPORTED_PARAMS)))

    # Build the dictionary to get the parameter constructor
    constructor_dict = {}
    constructor_dict[
        'preprocessed_sequence_illumina_params'] = PreprocessedIlluminaParams
    constructor_dict[
        'preprocessed_sequence_454_params'] = Preprocessed454Params
    constructor_dict[
        'processed_params_sortmerna'] = ProcessedSortmernaParams

    constructor = constructor_dict[table]

    try:
        params = dict(tuple(l.strip().split('\t')) for l in open(fp, 'U'))
    except ValueError:
        raise ValueError("The format of the parameters files is not correct. "
                         "The format is PARAMETER_NAME<tab>VALUE")

    return constructor.create(name, **params)


def update_preprocessed_data_from_cmd(sl_out_dir, study_id, ppd_id=None):
    """Updates the preprocessed data of the study 'study_id'

    Parameters
    ----------
    sl_out_dir : str
        The path to the split libraries output directory
    study_id : int
        The study_id of the study to be updated
    ppd_id : int, optional
        The id of the preprocessed_data to be updated. If not provided, the
        preprocessed data with the lowest id in the study will be updated.

    Returns
    -------
    qiita_db.PreprocessedData
        The updated preprocessed data

    Raises
    ------
    IOError
        If sl_out_dir does not contain all the required files
    ValueError
        If the study does not have any preprocessed data
        If ppd_id is provided and it does not belong to the given study
    """
    # Check that we have all the required files
    path_builder = partial(join, sl_out_dir)
    new_fps = {'preprocessed_fasta': path_builder('seqs.fna'),
               'preprocessed_fastq': path_builder('seqs.fastq'),
               'preprocessed_demux': path_builder('seqs.demux'),
               'log': path_builder('split_library_log.txt')}

    missing_files = [key for key, val in viewitems(new_fps) if not exists(val)]
    if missing_files:
        raise IOError(
            "The directory %s does not contain the following required files: "
            "%s" % (sl_out_dir, ', '.join(missing_files)))

    # Get the preprocessed data to be updated
    study = Study(study_id)
    ppds = study.preprocessed_data()
    if not ppds:
        raise ValueError("Study %s does not have any preprocessed data")

    if ppd_id:
        if ppd_id not in ppds:
            raise ValueError("The preprocessed data %d does not exist in "
                             "study %d. Available preprocessed data: %s"
                             % (ppd_id, study_id, ', '.join(map(str, ppds))))
        ppd = PreprocessedData(ppd_id)
    else:
        ppd = PreprocessedData(sorted(ppds)[0])

    # We need to loop through the fps list to get the db filepaths that we
    # need to modify
    fps = defaultdict(list)
    for fp_id, fp, fp_type in sorted(ppd.get_filepaths()):
        fps[fp_type].append((fp_id, fp))

    fps_to_add = []
    fps_to_modify = []
    keys = ['preprocessed_fasta', 'preprocessed_fastq', 'preprocessed_demux',
            'log']

    for key in keys:
        if key in fps:
            db_id, db_fp = fps[key][0]
            fp_checksum = compute_checksum(new_fps[key])
            fps_to_modify.append((db_id, db_fp, new_fps[key], fp_checksum))
        else:
            fps_to_add.append(
                (new_fps[key], convert_to_id(key, 'filepath_type')))

    # Insert the new files in the database, if any
    if fps_to_add:
        ppd.add_filepaths(fps_to_add)

    # Update the files and the database
    conn_handler = SQLConnectionHandler()
    # Create a queue so we can execute all the modifications on the DB in
    # a transaction block
    queue_name = "update_ppd_%d" % ppd.id
    conn_handler.create_queue(queue_name)
    sql = "UPDATE qiita.filepath SET checksum=%s WHERE filepath_id=%s"
    bkp_files = []
    for db_id, db_fp, new_fp, checksum in fps_to_modify:
        # Move the db_file in case something goes wrong
        bkp_fp = "%s.bkp" % db_fp
        move(db_fp, bkp_fp)
        bkp_files.append((bkp_fp, db_fp))

        # Start the update for the current file
        # Move the file to the database location
        move(new_fp, db_fp)
        # Add the SQL instruction to the DB
        conn_handler.add_to_queue(queue_name, sql, (checksum, db_id))

    # Execute the queue
    try:
        conn_handler.execute_queue(queue_name)
    except Exception:
        # We need to catch any exception so we can restore the db files
        for bkp_fp, db_fp in bkp_files:
            move(bkp_fp, db_fp)
        # Using just raise so the original traceback is shown
        raise

    # Since the files and the database have been updated correctly,
    # remove the backup files
    for bkp_fp, _ in bkp_files:
        remove(bkp_fp)

    return ppd
