from __future__ import division

# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

import sys
from collections import defaultdict
from heapq import heappush, heappop
from contextlib import contextmanager

import h5py
import numpy as np
import pandas as pd
from skbio.io.util import _is_string_or_bytes
from future.utils import viewitems
from natsort import natsorted


def per_sample_sequences(iter_, max_seqs, min_seqs=1, random_buf_size=100000):
    """Get a max random subset of per sample sequences

    Parameters
    ----------
    iter_ : skbio.parse.sequences.SequenceIterator
        The sequences to walk over
    max_seqs : unsigned int
        The maximum number of sequences per sample.
    min_seqs : unsigned int, optional
        The minimum number of sequences that must exist in a sample.
    random_buf_size : unsigned int, optional
        The size of the random value buffer.

    Notes
    -----
    Randomly get ``max_seqs`` for each sample. If the sample has less than
    ``max_seqs``, only those samples that have > ``min_seqs`` are returned.

    This method will at most hold ``max_seqs`` * N data, where N is the number
    of samples.

    All sequences associated to a sample have an equal probability of being
    retained.

    Raises
    ------
    ValueError
        If ``min_seqs`` is > ``max_seqs``.
    ValueError
        If ``min_seqs`` < 1 or if ``max_seqs`` < 1.

    Returns
    -------
    generator
        (sequence_id, sequence) where ``sequence_id`` is of the form
        sampleid_integer.
    """
    if min_seqs > max_seqs:
        raise ValueError("min_seqs cannot be > max_seqs!")
    if min_seqs < 1 or max_seqs < 1:
        raise ValueError("min_seqs and max_seqs must be > 0!")

    # buffer some random values
    random_values = np.random.randint(0, sys.maxint, random_buf_size)
    random_idx = 0

    result = defaultdict(list)
    for record in iter_:
        # get sequence ID, sample_id, sequence and heap
        sequence_id = record['SequenceID']
        sample_id = sequence_id.rsplit('_', 1)[0]
        sequence = record['Sequence']
        heap = result[sample_id]

        # pull a random value, and recompute random values if we've consumed
        # our buffer
        random_value = random_values[random_idx]
        random_idx += 1
        if random_idx >= random_buf_size:
            random_values = np.random.randint(0, sys.maxint, random_buf_size)
            random_idx = 0

        # push our sequence on to the heap and drop the smallest if necessary
        heappush(heap, (random_value, sequence_id, sequence))
        if len(heap) > max_seqs:
            heappop(heap)

    # yield the sequences
    for sid, heap in viewitems(result):
        if len(heap) < min_seqs:
            continue

        for _, sequence_id, sequence in heap:
            yield (sequence_id, sequence)


def stats_from_df(df):
    """Create a dictionary of summary statistics for a sample or prep template

    Parameters
    ----------
    t : SampleTemplate or PrepTemplate
        Sample or prep template object to summarize

    Returns
    -------
    dict
        Dictionary object where the keys are the names of the metadata
        categories and the keys are tuples where the first element is the name
        of a metadata value in category and the second element is the number of
        times that value was seen.
    """
    out = {}

    for column in natsorted(df.columns):
        counts = df[column].value_counts()

        # get a pandas series of the value-count pairs
        out[column] = [(key, counts[key]) for key in natsorted(counts.index)]

    return out


def metadata_stats_from_sample_and_prep_templates(st, pt):
    """Create a dictionary of summary statistics for the sample/prep templates

    Parameters
    ----------
    st : SampleTemplate
        Initialized SampleTemplate to use for the metadat stats.
    pt : PrepTemplate
        Initialized PrepTemplate to use for the metadat stats.

    Returns
    -------
    dict
        Dictionary object where the keys are the names of the metadata
        categories and the keys are tuples where the first element is the name
        of a metadata value in category and the second element is the number of
        times that value was seen.
    """
    df = metadata_map_from_sample_and_prep_templates(st, pt)
    return stats_from_df(df)


def metadata_map_from_sample_and_prep_templates(st, pt):
    """Create a mapping file from a sample and a prep template

    Parameters
    ----------
    st : SampleTemplate
        Initialized SampleTemplate to use.
    pt : PrepTemplate
        Initialized PrepTemplate to use.

    Returns
    -------
    pd.DataFrame
        A DataFrame object where the index values are the sample identifiers
        and the column names are the metadata categories.

    Notes
    -----
    If the sample and preparation templates include repeated column names these
    will be repeated in the resulting object, as they are not supposed to have
    overlapping column names.
    """
    s_df = dataframe_from_template(st)
    p_df = dataframe_from_template(pt)

    return pd.merge(s_df, p_df, left_index=True, right_index=True, how='outer')


def dataframe_from_template(t):
    """Get a dataframe from a sample or prep template

    Parameters
    ----------
    t : SampleTemplate, PrepTemplate
        Object to convert into a dataframe

    Returns
    -------
    pd.DataFrame
        A DataFrame object where the index values are the sample identifiers
        and the column names are the metadata categories.
    """
    t = template_to_dict(t)
    df = pd.DataFrame.from_dict(t, orient='index')
    return df


def template_to_dict(t):
    """Convert a SampleTemplate or PrepTemplate into a 2D-dictionary

    Parameters
    ----------
    t : SampleTemplate or PrepTemplate
        template to convert into a two-dimensional dictionary

    Returns
    -------
    dict
        dictionary object where the keys are the sample identifiers and the
        the values are dictionaries with each column name as the keys.

    """
    out = {}
    for sample_id, metadata in viewitems(t):
        out[sample_id] = {}
        for column_name, column_value in viewitems(metadata):
            # cast to string as a datetime object can be returned here
            out[sample_id][column_name] = str(column_value)
    return out


def _get_filehandle(filepath_or, *args, **kwargs):
    """Open file if `filepath_or` looks like a string/unicode/bytes, else
    pass through.
    """
    if _is_string_or_bytes(filepath_or):
        if h5py.is_hdf5(filepath_or):
            fh, own_fh = h5py.File(filepath_or, *args, **kwargs), True
        else:
            fh, own_fh = open(filepath_or, *args, **kwargs), True
    else:
        fh, own_fh = filepath_or, False
    return fh, own_fh


@contextmanager
def open_file(filepath_or, *args, **kwargs):
    """Context manager, like ``open``, but lets file handles and file like
    objects pass untouched.

    It is useful when implementing a function that can accept both
    strings and file-like objects (like numpy.loadtxt, etc).

    This method differs slightly from scikit-bio's implementation in that it
    handles HDF5 files appropriately.

    Parameters
    ----------
    filepath_or : str/bytes/unicode string or file-like
         If string, file to be opened using ``h5py.File`` if the file is an
         HDF5 file, otherwise builtin ``open`` will be used. If it is not a
         string, the object is just returned untouched.

    Other parameters
    ----------------
    args, kwargs : tuple, dict
        When `filepath_or` is a string, any extra arguments are passed
        on to the ``open`` builtin.

    Examples
    --------
    >>> with open_file('filename') as f:  # doctest: +SKIP
    ...     pass
    >>> fh = open('filename')             # doctest: +SKIP
    >>> with open_file(fh) as f:          # doctest: +SKIP
    ...     pass
    >>> fh.closed                         # doctest: +SKIP
    False
    >>> fh.close()                        # doctest: +SKIP

    """
    fh, own_fh = _get_filehandle(filepath_or, *args, **kwargs)
    try:
        yield fh
    finally:
        if own_fh:
            fh.close()
