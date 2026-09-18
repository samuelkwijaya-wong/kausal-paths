"""
The long-frame contract and the wide-CSV writer.

The validator is the last thing standing between a parsing mistake and a factor
table that loads cleanly into a city model and computes the wrong answer, so its
refusals are tested as carefully as its successes.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.



from pathlib import Path

import polars as pl
import pytest

from tools.us_factors.tidy import TidyFrameError, to_wide, validate_long, write_wide_csv


def long_frame(**overrides: object) -> pl.DataFrame:
    base = {
        'dataset': ['t', 't'],
        'metric': ['m', 'm'],
        'quantity': ['emission_factor', 'emission_factor'],
        'unit': ['lb/MWh', 'lb/MWh'],
        'egrid_subregion': ['AZNM', 'AZNM'],
        'year': [2021, 2022],
        'value': [1.0, 2.0],
        'source': ['US EPA eGRID2023', 'US EPA eGRID2023'],
        'comment': [None, None],
    }
    base.update(overrides)
    return pl.DataFrame(base, schema_overrides={'year': pl.Int32, 'comment': pl.String})


def test_accepts_a_well_formed_frame() -> None:
    validate_long(long_frame())


def test_pivots_years_into_columns_in_order() -> None:
    wide = to_wide(long_frame())

    assert wide.columns == [
        'Dataset', 'Metric', 'Quantity', 'Unit', 'egrid_subregion', '2021', '2022', 'Source', 'Comment',
    ]
    assert wide.height == 1


def test_year_columns_sort_numerically_not_lexically() -> None:
    """
    Year columns sort numerically.

    '2009' must come before '2010', which string sorting also gets right -- but
    a three-digit year or a sort on the pivot's own order would not.
    """
    df = long_frame(year=[2009, 2010], value=[1.0, 2.0])

    wide = to_wide(df)

    years = [c for c in wide.columns if c.isdigit()]
    assert years == ['2009', '2010']


def test_rejects_a_null_factor() -> None:
    """A null value is the failure that silently corrupts a model."""
    with pytest.raises(TidyFrameError, match="Column 'value' has 1 null"):
        validate_long(long_frame(value=[1.0, None]))


def test_rejects_an_empty_frame() -> None:
    with pytest.raises(TidyFrameError, match='empty'):
        validate_long(long_frame().head(0))


def test_rejects_mixed_units_within_one_metric() -> None:
    with pytest.raises(TidyFrameError, match='Mixed units'):
        validate_long(long_frame(unit=['lb/MWh', 'lb/GWh']))


def test_rejects_duplicate_keys() -> None:
    """Two values for the same region-year would silently drop one in the pivot."""
    with pytest.raises(TidyFrameError, match='duplicate'):
        validate_long(long_frame(year=[2021, 2021]))


def test_rejects_a_dimension_named_like_a_reserved_column() -> None:
    """
    A dimension may not take a reserved name.

    ``Comment`` is per-row metadata in the upload format, never a dimension. A
    dimension carrying that name would be silently swallowed on import.
    """
    df = long_frame().rename({'egrid_subregion': 'Comment'})

    with pytest.raises(TidyFrameError, match='reserved upload-format column'):
        validate_long(df)


def test_rejects_a_dimension_that_looks_like_a_year() -> None:
    df = long_frame().rename({'egrid_subregion': '2030'})

    with pytest.raises(TidyFrameError, match='read as a year column'):
        validate_long(df)


def test_writes_a_csv_with_blank_cells_for_missing_years(tmp_path: Path) -> None:
    """A region with no value in one year must leave the cell empty, not zero."""
    df = pl.concat([
        long_frame(),
        long_frame(egrid_subregion=['CAMX', 'CAMX'], year=[2021, 2023], value=[3.0, 4.0]),
    ], how='vertical')

    path = write_wide_csv(df, tmp_path / 'out.csv')
    text = path.read_text()

    header = text.splitlines()[0]
    assert header.startswith('Dataset,Metric,Quantity,Unit,egrid_subregion,2021,2022,2023')
    # AZNM has no 2023 value; the cell is empty rather than filled.
    aznm = next(line for line in text.splitlines() if 'AZNM' in line)
    assert aznm.endswith(',US EPA eGRID2023,')
    assert ',,' in aznm
