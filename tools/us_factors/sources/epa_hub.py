"""
EPA GHG Emission Factors Hub -- fuels, vehicles and waste.

The Hub is the workbook EPA republishes each year collecting the default factors
a US inventory needs outside of electricity: burning a fuel in a boiler, burning
it in a vehicle, and landfilling a ton of waste. It is the source behind most of
the numbers the existing US city configs carry by hand -- Sedona's "EPA factors
per MMBtu burned" (``configs/sedona.yaml:390``), Longmont's
``emission_factor_natural_gas``, Minneapolis's ``onroad_fuel_emission_factors``.

Why the tables are declared as data
-----------------------------------
The Hub is one workbook of many loosely-related tables, and EPA rewords its
headers and moves its sheets between editions far more freely than eGRID does.
So each table is a ``HubTable`` record -- which sheet, which key column, which
value columns and what they mean -- rather than bespoke parsing code. Adapting to
a new edition is then editing a declaration, which is the difference between a
five-minute fix and an afternoon.

Column matching is by *token*, not exact header text: a column declared as
``('kg', 'co2', 'mmbtu')`` matches ``kg CO2 per mmBtu`` and
``CO2 Factor (kg / mmBtu)`` alike, but will not silently match a CH4 column.
"""
# ruff: noqa: TC001, TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.


import re
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from tools.us_factors.provenance import SourceSpec, fetch
from tools.us_factors.sources.workbook import (
    HeaderedSheet,
    WorkbookLayoutError,
    find_sheet,
    open_workbook,
    read_headered,
)


@dataclass(frozen=True)
class ValueColumn:
    """One value column of a Hub table: how to find it, and what it holds."""

    tokens: tuple[str, ...]
    gas: str
    scale: float = 1.0
    """Multiplier onto the table's declared unit, for a column published in another."""

    note: str = ''


@dataclass(frozen=True)
class HubTable:
    """One table within the Hub workbook, and the dataset it becomes."""

    dataset: str
    metric: str
    quantity: str
    unit: str
    """The single unit of the resulting metric; the format allows only one."""

    sheet_pattern: str
    key_header: str
    """The header of the column naming each row, e.g. ``Fuel type``."""

    dimension: str
    """The dimension column the key becomes, e.g. ``fuel``."""

    columns: tuple[ValueColumn, ...]
    stop_at_blank: bool = True
    """Hub sheets stack several tables; stop at the first blank key to read only the first."""


STATIONARY = HubTable(
    dataset='epa_stationary_factors',
    metric='emission_factor',
    quantity='emission_factor',
    unit='kg/MMBtu',
    sheet_pattern=r'stationary',
    key_header='Fuel type',
    dimension='fuel',
    columns=(
        ValueColumn(('kg', 'co2', 'mmbtu'), 'co2'),
        # CH4 and N2O are published in grams; the metric carries kilograms.
        ValueColumn(('g', 'ch4', 'mmbtu'), 'ch4', scale=1e-3, note='published in g/MMBtu'),
        ValueColumn(('g', 'n2o', 'mmbtu'), 'n2o', scale=1e-3, note='published in g/MMBtu'),
    ),
)

MOBILE_MILEAGE = HubTable(
    dataset='epa_mobile_mileage_factors',
    metric='emission_factor',
    quantity='emission_factor',
    # Published by EPA as grams per mile, declared here as grams per vehicle-mile.
    # `VMT` is `vehicle * mile` in the model's registry, and it is the unit the
    # city models already use for this quantity (Sedona and Longmont both write
    # `g/VMT`), so the library meets them where they are rather than handing every
    # consumer a dimension mismatch to resolve.
    unit='g/VMT',
    sheet_pattern=r'mobile',
    key_header='Vehicle Type',
    dimension='vehicle_type',
    columns=(
        ValueColumn(('g', 'ch4', 'mile'), 'ch4'),
        ValueColumn(('g', 'n2o', 'mile'), 'n2o'),
    ),
)

TABLES: tuple[HubTable, ...] = (STATIONARY, MOBILE_MILEAGE)
"""
The tables read today.

Deliberately a short list. Mobile CO2 (per gallon) and the waste factors are the
obvious next additions, and each is a new ``HubTable`` record plus a test -- but
declaring a table whose layout has not been checked against the real workbook
would be guessing, and this package does not guess about factors.
"""

SPEC = SourceSpec(
    key='epa_ghg_emission_factors_hub',
    # Verify against https://www.epa.gov/climateleadership/ghg-emission-factors-hub
    # before a first run; EPA re-posts this workbook annually under a dated path.
    url='https://www.epa.gov/system/files/documents/2025-01/ghg-emission-factors-hub-2025.xlsx',
    authority='US EPA',
    edition='GHG Emission Factors Hub 2025',
    citation=(
        'US Environmental Protection Agency, Center for Corporate Climate Leadership, '
        'GHG Emission Factors Hub (2025 edition).'
    ),
)


def slugify(label: str) -> str:
    """Turn a published label into a dimension category id: ``Natural Gas`` -> ``natural_gas``."""
    return re.sub(r'[^a-z0-9]+', '_', str(label).strip().lower()).strip('_')


def _resolve_columns(sheet: HeaderedSheet, table: HubTable) -> tuple[str, list[tuple[ValueColumn, str]]]:
    """Return the key column and the value columns of ``table`` present in ``sheet``."""
    resolved = [
        (column, name)
        for column in table.columns
        if (name := sheet.find_by_tokens(column.tokens)) is not None
    ]
    if not resolved:
        raise WorkbookLayoutError(
            f"Table '{table.dataset}': none of the declared value columns "
            f'{[c.tokens for c in table.columns]} matched.\n'
            f"  Sheet '{sheet.title}' columns: {sorted(sheet.columns)[:40]}"
        )

    key_name = sheet.find_by_tokens((table.key_header,))
    if key_name is None:  # pragma: no cover - read_headered already anchored on it
        raise WorkbookLayoutError(f"Table '{table.dataset}': key column '{table.key_header}' vanished.")
    return key_name, resolved


def _row_records(
    row: dict[str, object],
    label: object,
    resolved: list[tuple[ValueColumn, str]],
    table: HubTable,
    source_label: str,
    data_year: int,
) -> list[dict[str, object]]:
    """Turn one spreadsheet row into one tidy record per gas present in it."""
    out: list[dict[str, object]] = []
    for column, name in resolved:
        value = row.get(name)
        if value is None or isinstance(value, str):
            continue
        note = f'{table.key_header}: {label}'
        if column.note:
            note += f'; {column.note}'
        out.append({
            'dataset': table.dataset,
            'metric': table.metric,
            'quantity': table.quantity,
            'unit': table.unit,
            table.dimension: slugify(str(label)),
            'greenhouse_gas': column.gas,
            'year': data_year,
            'value': float(value) * column.scale,
            'source': source_label,
            'comment': note,
        })
    return out


def parse_table(path: Path, table: HubTable, source_label: str, data_year: int) -> pl.DataFrame:
    """Parse one declared table out of the Hub workbook."""
    workbook = open_workbook(path)
    sheet: HeaderedSheet = read_headered(find_sheet(workbook, table.sheet_pattern), table.key_header)
    key_name, resolved = _resolve_columns(sheet, table)

    records: list[dict[str, object]] = []
    for row in sheet.rows():
        label = row.get(key_name)
        if label is None or not str(label).strip():
            if table.stop_at_blank and records:
                break
            continue
        records.extend(_row_records(row, label, resolved, table, source_label, data_year))

    if not records:
        raise WorkbookLayoutError(
            f"Table '{table.dataset}': parsed no rows from sheet '{sheet.title}'."
        )
    return pl.DataFrame(records, schema_overrides={'year': pl.Int32, 'value': pl.Float64})


def build(
    data_year: int,
    *,
    tables: tuple[HubTable, ...] = TABLES,
    refresh: bool = False,
    offline: bool = False,
) -> dict[str, pl.DataFrame]:
    """
    Fetch the Hub workbook and parse each declared table.

    Returns one frame per dataset rather than a single concatenation: the tables
    have different dimensions, and merging them would put a ``fuel`` column on a
    per-mile vehicle factor.
    """
    retrieval = fetch(SPEC, refresh=refresh, offline=offline)
    out: dict[str, pl.DataFrame] = {}
    for table in tables:
        print(f'  {SPEC.edition} -> {table.dataset} ({retrieval.path.name})')
        out[table.dataset] = parse_table(retrieval.path, table, SPEC.source_label(), data_year)
    return out
