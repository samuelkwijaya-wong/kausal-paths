"""
EPA eGRID -- grid electricity emission factors by subregion.

eGRID is the source every US city inventory uses for the emissions attributable
to a kilowatt-hour off the grid. It publishes a rate per eGRID subregion, of
which there are 27; a city picks the one its utility sits in. That per-region
structure is the one real difference from the German library, whose factors are
national scalars, and it is why the published table carries an
``egrid_subregion`` dimension for the city to filter on.

What this reads
---------------
The subregion sheet (``SRL23`` in eGRID2023, ``SRL22`` in eGRID2022, ...), whose
rows are subregions and whose columns are emission rates. The codes are stable
across releases even as the sheet name moves:

    SUBRGN     subregion acronym
    SRNAME     subregion name
    SRCO2RTA   annual CO2 total output emission rate   (lb/MWh)
    SRCH4RTA   annual CH4 total output emission rate   (lb/GWh)
    SRN2ORTA   annual N2O total output emission rate   (lb/GWh)
    SRC2ERTA   annual CO2-equivalent total output rate (lb/MWh)

**Total output**, not combustion output: it divides emissions by *all* generation
including nuclear and renewables, which is the right basis for a consumption
inventory and the one a city means by "the grid factor". The combustion-output
rates in the same sheet answer a different question and are not read here.

Vintages
--------
An eGRID release reports one data year, and releases lag it by roughly two years.
Cities apply them inconsistently -- Sedona's config records that its workbook gave
2020 and 2021 the same eGRID2020 figures, then took each following year from the
release published the year before (``configs/sedona.yaml:251``). Rather than
encode any such policy, this parser emits one row per *data year*, labelled with
the release it came from. A city that wants a different vintage policy overrides
locally, and can see from the ``Source`` column what it is overriding.
"""
# ruff: noqa: TC001, TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.


from dataclasses import dataclass
from pathlib import Path

import polars as pl

from tools.us_factors.provenance import Retrieval, SourceSpec, fetch
from tools.us_factors.regions import is_known_subregion
from tools.us_factors.sources.workbook import (
    HeaderedSheet,
    WorkbookLayoutError,
    find_sheet,
    open_workbook,
    read_headered,
)

DATASET = 'egrid_grid_factors'
SUBREGION_ANCHOR = 'SUBRGN'


METRIC_UNIT = 'lb/MWh'
"""
The single unit every row of the grid table carries.

The upload format allows one unit per (Dataset, Metric) -- mixed units inside a
metric are rejected by ``upload_new_dataset.py`` -- and the gases here share one
metric because they are distinguished by the ``greenhouse_gas`` dimension. So the
per-GWh rates are converted on the way in rather than carried as published.
"""


@dataclass(frozen=True)
class RateColumn:
    """One emission-rate column of the subregion sheet, and what it means."""

    code: str
    gas: str
    published_unit: str
    scale: float = 1.0
    """Multiplier onto ``METRIC_UNIT``. 1/1000 converts a lb/GWh rate to lb/MWh."""


RATE_COLUMNS = (
    RateColumn('SRCO2RTA', 'co2', 'lb/MWh'),
    RateColumn('SRCH4RTA', 'ch4', 'lb/GWh', scale=1e-3),
    RateColumn('SRN2ORTA', 'n2o', 'lb/GWh', scale=1e-3),
    RateColumn('SRC2ERTA', 'co2e', 'lb/MWh'),
)
"""
The total-output annual rates, one per gas.

EPA publishes CH4 and N2O per GWh rather than per MWh, because per MWh they would
be small fractions. Each row records its published unit and the conversion in the
``Comment`` column, so a value in the table can still be checked against the EPA
sheet it came from without reverse-engineering the arithmetic.
"""


def spec_for_release(year: int) -> SourceSpec:
    """
    Return the download spec for one eGRID release.

    The URL is EPA's ``system/files`` path, which embeds the month the release was
    posted -- so it cannot be derived from the year alone and is recorded per
    release in ``RELEASE_URLS``. A release not listed there is still usable: place
    the workbook in the cache directory by hand and build with ``--offline``.
    """
    url = RELEASE_URLS.get(year)
    if url is None:
        known = ', '.join(str(y) for y in sorted(RELEASE_URLS))
        raise WorkbookLayoutError(
            f'No download URL recorded for eGRID{year}. Known releases: {known}.\n'
            f'Add it to RELEASE_URLS, or place the workbook at cache/egrid{year}.xlsx '
            'and build with --offline.'
        )
    return SourceSpec(
        key=f'egrid{year}',
        url=url,
        authority='US EPA',
        edition=f'eGRID{year}',
        citation=(
            f'US Environmental Protection Agency, Emissions & Generation Resource '
            f'Integrated Database (eGRID{year}). Washington, DC.'
        ),
    )


RELEASE_URLS: dict[int, str] = {
    # Verify each URL against https://www.epa.gov/egrid/download-data before a
    # first run: EPA re-posts workbooks under new dated paths without redirects.
    2023: 'https://www.epa.gov/system/files/documents/2025-01/egrid2023_data.xlsx',
    2022: 'https://www.epa.gov/system/files/documents/2024-01/egrid2022_data.xlsx',
    2021: 'https://www.epa.gov/system/files/documents/2023-01/egrid2021_data.xlsx',
}
"""
Known eGRID release download URLs, newest first.

Deliberately a small explicit table rather than a guessed URL pattern. A wrong
guess that happens to resolve would import the wrong vintage silently.
"""


def find_subregion_sheet(workbook: object, release_year: int) -> HeaderedSheet:
    """
    Locate the subregion sheet of an eGRID workbook.

    Tries the release's own naming (``SRL23`` for 2023) first, then falls back to
    any ``SRL*`` sheet, so a release that names it differently still parses.
    """
    suffix = f'{release_year % 100:02d}'
    for pattern in (rf'^SRL{suffix}$', r'^SRL\d*$', r'SRL'):
        try:
            sheet = find_sheet(workbook, pattern)
        except WorkbookLayoutError:
            continue
        return read_headered(sheet, SUBREGION_ANCHOR)
    raise WorkbookLayoutError(
        f'No eGRID subregion sheet (SRL*) found for release {release_year}.\n'
        f'  Sheets present: {getattr(workbook, "sheetnames", "unknown")}'
    )


def parse(path: Path, release_year: int, data_year: int, source_label: str) -> pl.DataFrame:
    """
    Parse one eGRID workbook into the long frame contract of ``tidy.py``.

    ``data_year`` is the year the release *reports on*, which is what the row is
    labelled with -- not ``release_year``, which only identifies the edition.
    """
    workbook = open_workbook(path)
    sheet = find_subregion_sheet(workbook, release_year)

    available = [c for c in RATE_COLUMNS if sheet.has(c.code)]
    if not available:
        raise WorkbookLayoutError(
            f"Sheet '{sheet.title}' has none of the expected rate columns "
            f'{[c.code for c in RATE_COLUMNS]}.\n'
            f'  Columns present: {sorted(sheet.columns)[:40]}'
        )

    records: list[dict[str, object]] = []
    unknown: set[str] = set()
    for row in sheet.rows():
        code = row.get('subrgn')
        if code is None or not str(code).strip():
            continue
        code = str(code).strip().upper()
        # eGRID sheets repeat the header codes in a second descriptive row; it
        # fails this check and is skipped, as are any total/footnote rows.
        if not is_known_subregion(code):
            unknown.add(code)
            continue
        for rate in available:
            value = row.get(rate.code.lower())
            if value is None or isinstance(value, str):
                continue
            note = f'{rate.code}, total output rate'
            if rate.scale != 1.0:
                note += f'; published as {rate.published_unit}, x{rate.scale:g} to {METRIC_UNIT}'
            records.append({
                'dataset': DATASET,
                'metric': 'grid_emission_factor',
                'quantity': 'emission_factor',
                'unit': METRIC_UNIT,
                # Lower-cased because Paths dimension category ids are lower-case
                # by convention (see the `consumer_sector` categories in
                # configs/sedona.yaml). The published upper-case acronym is kept
                # as the category's label in the shared config fragment.
                'egrid_subregion': code.lower(),
                'greenhouse_gas': rate.gas,
                'year': data_year,
                'value': float(value) * rate.scale,
                'source': source_label,
                'comment': note,
            })

    if not records:
        raise WorkbookLayoutError(
            f"Parsed no rows from '{sheet.title}'. Unrecognised subregion codes seen: "
            f'{sorted(unknown) or "none"}'
        )
    if unknown:
        # Loud, but not fatal: EPA footnote rows land here legitimately. A genuine
        # new subregion also lands here, and must be added to regions.py.
        print(f'  note: skipped unrecognised subregion codes {sorted(unknown)}')

    return pl.DataFrame(records, schema_overrides={'year': pl.Int32, 'value': pl.Float64})


def build(
    release_years: list[int],
    *,
    data_years: dict[int, int] | None = None,
    refresh: bool = False,
    offline: bool = False,
) -> pl.DataFrame:
    """
    Fetch and parse several eGRID releases into one long frame.

    ``data_years`` maps a release to the year it reports on; the default assumes
    the release year *is* the data year, which is how EPA names them (eGRID2023
    reports 2023 data, published 2025).
    """
    data_years = data_years or {}
    frames: list[pl.DataFrame] = []
    for release in sorted(release_years):
        spec = spec_for_release(release)
        retrieval: Retrieval = fetch(spec, refresh=refresh, offline=offline)
        data_year = data_years.get(release, release)
        print(f'  eGRID{release} -> data year {data_year} ({retrieval.path.name})')
        frames.append(parse(retrieval.path, release, data_year, spec.source_label()))
    return pl.concat(frames, how='vertical')
