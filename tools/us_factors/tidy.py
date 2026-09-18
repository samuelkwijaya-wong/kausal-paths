"""
The shared row contract, and the writer that turns it into an upload CSV.

Every source module parses its workbook into the same long-format frame, one row
per (table, metric, dimensions, year). ``write_wide_csv`` then pivots years into
columns to produce the format ``tools/upload_new_dataset.py`` reads, specified in
``docs/dataset-csv-format.md``:

    Dataset, Metric, Quantity, Unit, <dimension columns...>, <year columns...>, Source, Comment

Keeping the sources on a long frame and pivoting once here means a source module
never has to know which years the others cover, and a dimension column appears in
the output only for the tables that actually use it.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.



from pathlib import Path

import polars as pl

LONG_SCHEMA: dict[str, pl.DataType] = {
    'dataset': pl.String,
    'metric': pl.String,
    'quantity': pl.String,
    'unit': pl.String,
    'year': pl.Int32,
    'value': pl.Float64,
    'source': pl.String,
    'comment': pl.String,
}
"""The non-dimension columns every source must produce. Anything else is a dimension."""

RESERVED_OUTPUT_COLUMNS = ('Dataset', 'Metric', 'Quantity', 'Unit', 'Source', 'Comment')
"""
Column names the upload format reserves.

``Source`` and ``Comment`` are in ``RESERVED_ROW_COLUMNS`` (``src/nodes/constants.py``),
so they ride through as per-row metadata rather than being read as dimensions.
Every other column that is not a year is read as a dimension, which is why a
dimension must never be named one of these.
"""


class TidyFrameError(ValueError):
    """A source produced a frame that does not satisfy the contract."""


def dimension_columns(df: pl.DataFrame) -> list[str]:
    """Return the dimension columns of a long frame: everything not in ``LONG_SCHEMA``."""
    return [c for c in df.columns if c not in LONG_SCHEMA]


def validate_long(df: pl.DataFrame) -> None:
    """
    Check a source's long frame before it reaches the writer.

    These are structural checks only. They cannot tell a right factor from a
    wrong one -- that is what the source-specific tests and the phase-2
    comparison against the existing city models are for -- but they do catch the
    failure that silently corrupts a model: a null where a factor should be.
    """
    missing = [c for c in LONG_SCHEMA if c not in df.columns]
    if missing:
        raise TidyFrameError(f'Long frame is missing required columns: {missing}')

    if df.is_empty():
        raise TidyFrameError('Long frame is empty; a source that parsed nothing is a failure, not an empty table.')

    for col in ('dataset', 'metric', 'quantity', 'unit', 'year', 'value', 'source'):
        n_null = df[col].null_count()
        if n_null:
            raise TidyFrameError(f"Column '{col}' has {n_null} null(s); every factor needs one.")

    for dim in dimension_columns(df):
        if dim in RESERVED_OUTPUT_COLUMNS:
            raise TidyFrameError(
                f"Dimension column '{dim}' collides with a reserved upload-format column "
                f'({", ".join(RESERVED_OUTPUT_COLUMNS)}).'
            )
        if dim.isdigit():
            raise TidyFrameError(f"Dimension column '{dim}' would be read as a year column.")

    # One unit per (dataset, metric): mixed units inside a metric are an error in
    # the upload format, and finding out here names the offending pair.
    mixed = (
        df.group_by('dataset', 'metric')
        .agg(pl.col('unit').n_unique().alias('n_units'))
        .filter(pl.col('n_units') > 1)
    )
    if not mixed.is_empty():
        pairs = ', '.join(f'{r["dataset"]}/{r["metric"]}' for r in mixed.iter_rows(named=True))
        raise TidyFrameError(f'Mixed units within a metric: {pairs}')

    dims = dimension_columns(df)
    duplicated = df.group_by(['dataset', 'metric', 'year', *dims]).len().filter(pl.col('len') > 1)
    if not duplicated.is_empty():
        raise TidyFrameError(
            f'{duplicated.height} duplicate (dataset, metric, year, dimensions) key(s); '
            'the first is ' + repr(duplicated.row(0, named=True))
        )


def to_wide(df: pl.DataFrame) -> pl.DataFrame:
    """Pivot a validated long frame into the upload CSV's wide shape."""
    validate_long(df)
    dims = dimension_columns(df)
    index = ['dataset', 'metric', 'quantity', 'unit', *dims, 'source', 'comment']

    wide = df.pivot(on='year', index=index, values='value', aggregate_function='first')

    year_cols = sorted((c for c in wide.columns if c not in index), key=int)
    renames = {
        'dataset': 'Dataset',
        'metric': 'Metric',
        'quantity': 'Quantity',
        'unit': 'Unit',
        'source': 'Source',
        'comment': 'Comment',
    }
    ordered = ['dataset', 'metric', 'quantity', 'unit', *dims, *year_cols, 'source', 'comment']
    return wide.select(ordered).rename(renames).sort(['Dataset', 'Metric', *dims])


def write_wide_csv(df: pl.DataFrame, path: Path) -> Path:
    """Write a long frame out as one upload CSV. Returns the path written."""
    wide = to_wide(df)
    path.parent.mkdir(parents=True, exist_ok=True)
    # null_value='' matches what the extractor scripts in data/ write, and is what
    # upload_new_dataset.py reads back as "no value for this year".
    wide.write_csv(path, null_value='')
    return path
