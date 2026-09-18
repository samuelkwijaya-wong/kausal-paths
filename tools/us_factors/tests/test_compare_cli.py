"""
The comparison CLI's data handling: reading wide CSVs and attributing them.

The wide-to-long step is where an export and a library table meet, so it has to
accept both spellings of the shared format -- the library writes lowercase
internal names and the upload format's capitalised ones.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations` in new
# files, and without it the flake8-type-checking fixes are not available.



from pathlib import Path

import polars as pl
import pytest

from tools.us_factors.compare_to_cities import group_by_instance, load_dir, to_long


def write_csv(path: Path, text: str) -> Path:
    path.write_text(text.strip() + '\n')
    return path


def test_wide_csv_becomes_one_row_per_year(tmp_path: Path) -> None:
    path = write_csv(tmp_path / 'a.csv', """
Dataset,Metric,Quantity,Unit,egrid_subregion,2022,2023,Source,Comment
egrid_grid_factors,grid_emission_factor,emission_factor,lb/MWh,AZNM,700.0,690.0,US EPA,
""")

    long = to_long(pl.read_csv(path))

    assert long.height == 2
    assert sorted(long['year'].to_list()) == [2022, 2023]
    assert long['dataset'].unique().to_list() == ['egrid_grid_factors']


def test_capitalised_format_columns_are_folded_to_the_internal_names(tmp_path: Path) -> None:
    path = write_csv(tmp_path / 'a.csv', """
Dataset,Metric,Unit,2022,Source
d,m,lb/MWh,1.0,S
""")

    long = to_long(pl.read_csv(path))

    for column in ('dataset', 'metric', 'unit', 'source'):
        assert column in long.columns


def test_blank_year_cells_do_not_become_rows(tmp_path: Path) -> None:
    """An empty cell means the city has no value that year, not a zero."""
    path = write_csv(tmp_path / 'a.csv', """
Dataset,Metric,Unit,2022,2023,Source
d,m,lb/MWh,700.0,,S
""")

    long = to_long(pl.read_csv(path))

    assert long.height == 1
    assert long['year'].item() == 2022


def test_a_csv_with_no_year_columns_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path / 'a.csv', 'Dataset,Metric,Unit\nd,m,lb/MWh')

    with pytest.raises(ValueError, match='No year columns'):
        to_long(pl.read_csv(path))


def test_unreadable_files_are_skipped_not_fatal(tmp_path: Path) -> None:
    write_csv(tmp_path / 'good.csv', """
Dataset,Metric,Unit,2022,Source
d/x,m,lb/MWh,1.0,S
""")
    write_csv(tmp_path / 'bad.csv', 'Dataset,Metric\nd,m')

    frames = load_dir(tmp_path)

    assert len(frames) == 1


def test_frames_are_attributed_by_dataset_namespace(tmp_path: Path) -> None:
    """A directory may hold exports for several cities at once."""
    write_csv(tmp_path / 'mixed.csv', """
Dataset,Metric,Unit,2022,Source
sedona/grid,m,lb/MWh,1.0,S
minneapolis/electricity,m,t_co2e/MWh,2.0,S
""")

    grouped = group_by_instance(load_dir(tmp_path))

    assert set(grouped) == {'sedona', 'minneapolis'}
    assert grouped['sedona']['value'].item() == 1.0


def test_a_dataset_without_a_namespace_is_ignored(tmp_path: Path) -> None:
    write_csv(tmp_path / 'a.csv', """
Dataset,Metric,Unit,2022,Source
no_namespace,m,lb/MWh,1.0,S
""")

    assert group_by_instance(load_dir(tmp_path)) == {}
