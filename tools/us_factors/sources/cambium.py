"""
NREL Cambium -- projected grid emission factors to 2050.

eGRID says what the grid emitted last year. Every Paths model runs to 2030 or
2050, so a library of historical factors alone leaves a city with one choice:
hold the grid flat for twenty-five years, which is what Sedona does today ("no
forecast method here: 2025-2030 is the last inventory year held flat",
``configs/sedona.yaml``). Held flat, a grid that is in fact decarbonising makes
every electricity-reduction action look better than it is, and every fuel-switch
action look worse.

Cambium fills that gap: annual emission rates per region out to 2050, under
several scenarios. Yolo is the clearest case in the repo -- one historical year
(2022) and a model that runs to 2045.

Average vs. long-run marginal
-----------------------------
Cambium publishes both, and they answer different questions. The **average**
rate (``aer_``) is the one that matches an inventory: it attributes a share of
total system emissions to each MWh consumed, which is what eGRID's total-output
rate does and what a GPC-conformant inventory wants. The **long-run marginal**
rate (``lrmer_``) estimates the emissions caused by a *change* in consumption,
which is the right basis for judging an action's impact but does not sum to the
system total.

This parser reads the average rate by default, because the library's first job is
continuity with the historical eGRID series a city's inventory already uses.
The marginal rate is available by declaring it, and a model that wants it should
say so deliberately rather than inherit it.

Obtaining the file
------------------
Cambium sits behind NREL's Scenario Viewer, which requires accepting its terms
before download -- there is no URL a script can GET. So this is a
``ManualSourceSpec``: download the annual, GEA-region CSV yourself and drop it in
the cache directory. The build then reads it like any other source.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.


from dataclasses import dataclass
from pathlib import Path

import polars as pl

from tools.us_factors.provenance import ManualSourceSpec, fetch
from tools.us_factors.sources.workbook import WorkbookLayoutError, normalise

DATASET = 'grid_factor_projection'

SPEC = ManualSourceSpec(
    key='cambium_annual_gea',
    url='https://scenarioviewer.nrel.gov/',
    authority='NREL',
    edition='Cambium 2023',
    citation=(
        'Gagnon, P., et al. (2024). Cambium 2023 Scenario Descriptions and '
        'Documentation. National Renewable Energy Laboratory, NREL/TP-6A40-88507.'
    ),
    suffix='.csv',
    instructions=(
        'Download from https://scenarioviewer.nrel.gov/ -- choose the Cambium '
        'dataset, "Annual" resolution and the GEA region aggregation, then save the '
        "CSV as cambium_annual_gea.csv in this package's cache/ directory. "
        'NREL requires accepting its terms, so this cannot be scripted.'
    ),
)


@dataclass(frozen=True)
class RateSeries:
    """One Cambium emission-rate column, and the basis it represents."""

    tokens: tuple[str, ...]
    basis: str
    note: str


AVERAGE_CO2E = RateSeries(
    tokens=('aer', 'co2e'),
    basis='average',
    note='average emission rate; comparable with eGRID total output',
)
LONG_RUN_MARGINAL_CO2E = RateSeries(
    tokens=('lrmer', 'co2e'),
    basis='long_run_marginal',
    note='long-run marginal emission rate; for judging the impact of a change in load',
)

REGION_TOKENS = ('gea',)
YEAR_TOKENS = ('t',)
METRIC_UNIT = 'kg/MWh'
"""
Cambium publishes these rates in kg CO2e per MWh.

Verify against the file's own header on a first run -- ``build_csv.py --inspect``
prints it -- because a unit misread here is a factor-of-1000 error that still
computes.
"""


def _resolve(columns: list[str], tokens: tuple[str, ...], what: str) -> str:
    wanted = [normalise(t) for t in tokens]
    hits = [c for c in columns if all(t in normalise(c).split() for t in wanted)]
    if not hits:
        loose = [c for c in columns if all(t in normalise(c) for t in wanted)]
        hits = loose
    if not hits:
        raise WorkbookLayoutError(
            f'Cambium CSV has no {what} column matching {tokens}.\n  Columns: {columns[:40]}'
        )
    if len(hits) > 1:
        raise WorkbookLayoutError(
            f'Cambium {what} tokens {tokens} matched several columns: {hits}.'
        )
    return hits[0]


def parse(
    path: Path,
    *,
    scenario: str,
    source_label: str,
    series: RateSeries = AVERAGE_CO2E,
) -> pl.DataFrame:
    """Parse a Cambium annual GEA-region CSV into the long frame contract."""
    raw = pl.read_csv(path, infer_schema_length=2000)
    columns = raw.columns

    region_col = _resolve(columns, REGION_TOKENS, 'region')
    year_col = _resolve(columns, YEAR_TOKENS, 'year')
    value_col = _resolve(columns, series.tokens, f'{series.basis} rate')

    df = (
        raw.select(
            pl.col(region_col).cast(pl.String).str.strip_chars().alias('cambium_region'),
            pl.col(year_col).cast(pl.Int32).alias('year'),
            pl.col(value_col).cast(pl.Float64).alias('value'),
        )
        .drop_nulls()
        .with_columns(
            pl.lit(DATASET).alias('dataset'),
            pl.lit('grid_emission_factor').alias('metric'),
            pl.lit('emission_factor').alias('quantity'),
            pl.lit(METRIC_UNIT).alias('unit'),
            pl.lit(scenario).alias('scenario'),
            pl.lit('co2e').alias('greenhouse_gas'),
            pl.lit(source_label).alias('source'),
            pl.lit(f'{value_col}; {series.note}').alias('comment'),
        )
    )

    if df.is_empty():
        raise WorkbookLayoutError(
            f'Cambium CSV at {path} yielded no rows after selecting '
            f'{region_col}/{year_col}/{value_col}.'
        )
    return df


def build(
    *,
    scenario: str = 'mid_case',
    series: RateSeries = AVERAGE_CO2E,
    refresh: bool = False,
    offline: bool = False,
) -> pl.DataFrame:
    """Read the manually-placed Cambium CSV and parse it."""
    retrieval = fetch(SPEC, refresh=refresh, offline=offline)
    print(f'  {SPEC.edition} -> {DATASET} ({retrieval.path.name}, {series.basis})')
    return parse(retrieval.path, scenario=scenario, source_label=SPEC.source_label(), series=series)
