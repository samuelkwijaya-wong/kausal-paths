"""
End to end: a source workbook through the parsers to an upload-format CSV.

The unit tests check each parser in isolation. This checks the thing that
actually has to work -- that what comes out the far end is a file
``tools/upload_new_dataset.py`` can read, with the dimension columns a city
config will filter on.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.



from pathlib import Path

import polars as pl

from tools.us_factors.sources import egrid, epa_hub
from tools.us_factors.tidy import write_wide_csv

SOURCE = 'US EPA eGRID2023'


def test_egrid_round_trips_to_a_readable_upload_csv(egrid_workbook: Path, tmp_path: Path) -> None:
    df = egrid.parse(egrid_workbook, release_year=2023, data_year=2023, source_label=SOURCE)

    path = write_wide_csv(df, tmp_path / 'egrid_grid_factors.csv')
    back = pl.read_csv(path)

    # The columns the upload format routes on, plus the two dimensions a city needs.
    for column in ('Dataset', 'Metric', 'Quantity', 'Unit', 'Source', 'Comment'):
        assert column in back.columns
    assert 'egrid_subregion' in back.columns
    assert 'greenhouse_gas' in back.columns
    assert '2023' in back.columns

    assert back['Dataset'].unique().to_list() == ['egrid_grid_factors']
    assert back['Quantity'].unique().to_list() == ['emission_factor']
    assert back.height == 3 * 4


def test_a_city_can_filter_the_shared_table_down_to_its_own_region(
    egrid_workbook: Path, tmp_path: Path
) -> None:
    """
    Select one region out of the shared table.

    The whole point of the shared table: one row per region, so a city selects
    its own with a `filters:` entry on the dataset binding rather than getting a
    private copy of the numbers.
    """
    df = egrid.parse(egrid_workbook, release_year=2023, data_year=2023, source_label=SOURCE)
    path = write_wide_csv(df, tmp_path / 'egrid_grid_factors.csv')

    back = pl.read_csv(path)
    sedona = back.filter(pl.col('egrid_subregion') == 'AZNM')

    assert sedona.height == 4  # one row per gas
    assert sedona.filter(pl.col('greenhouse_gas') == 'co2')['2023'].item() == 700.0


def test_hub_tables_keep_their_own_dimensions_separate(
    epa_hub_workbook: Path, tmp_path: Path
) -> None:
    """A per-mile vehicle factor must not acquire a `fuel` column, or vice versa."""
    stationary = epa_hub.parse_table(epa_hub_workbook, epa_hub.STATIONARY, SOURCE, data_year=2025)
    mileage = epa_hub.parse_table(epa_hub_workbook, epa_hub.MOBILE_MILEAGE, SOURCE, data_year=2025)

    stationary_csv = pl.read_csv(write_wide_csv(stationary, tmp_path / 'stationary.csv'))
    mileage_csv = pl.read_csv(write_wide_csv(mileage, tmp_path / 'mileage.csv'))

    assert 'fuel' in stationary_csv.columns
    assert 'vehicle_type' not in stationary_csv.columns
    assert 'vehicle_type' in mileage_csv.columns
    assert 'fuel' not in mileage_csv.columns


def test_every_value_carries_its_provenance(egrid_workbook: Path, tmp_path: Path) -> None:
    """A factor with no recorded source is indistinguishable from an invented one."""
    df = egrid.parse(egrid_workbook, release_year=2023, data_year=2023, source_label=SOURCE)

    back = pl.read_csv(write_wide_csv(df, tmp_path / 'out.csv'))

    assert back['Source'].null_count() == 0
    assert back['Source'].unique().to_list() == [SOURCE]
