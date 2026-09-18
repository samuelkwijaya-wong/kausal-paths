r"""
Whether the library reproduces what the city models already use.

This is the question that decides whether the library is adoptable. A shared
table is only worth having if it agrees with the hand-copied numbers where those
are right, and can say precisely where it does not.

The comparison is deliberately arithmetic and boring: pick one series out of the
library, pick the matching series out of a city's exported dataset, convert to a
common unit and subtract. What makes it useful is that it reports four outcomes
rather than two -- agrees, differs, could not be compared, and not present on one
side -- because in practice most of the interesting findings are in the last two.

Inputs
------
Both sides arrive as long frames. The library side comes from ``tables/``; the
city side from the existing round-trip tooling::

    python manage.py export_dataset sedona sedona/grid_emission_factors \\
        --out /tmp/sedona --format wide

Nothing here talks to a database or to DVC, so the comparison can be re-run on a
laptop against an export made weeks earlier.
"""

from dataclasses import dataclass, field

import pint
import polars as pl

from tools.us_factors.units import convert

DEFAULT_TOLERANCE = 0.005
"""
Relative difference below which two factors are called the same.

Half a percent. Published factors are quoted to three or four significant
figures and a city may have rounded on the way in, so an exact match is not the
right test; anything larger than this is a real difference in the number rather
than in its spelling.
"""


class Verdict:
    """The outcome of comparing one (series, year)."""

    AGREES = 'agrees'
    DIFFERS = 'differs'
    INCOMPARABLE = 'incomparable units'
    CITY_ONLY = 'city only'
    LIBRARY_ONLY = 'library only'


@dataclass(frozen=True)
class FactorMapping:
    """
    A claim that one city series and one library series are the same factor.

    The claim is the interesting part, and it is a human judgement: that
    Sedona's ``grid_emission_factor`` is the AZNM total-output CO2e rate is
    something a person asserts from reading the model, not something the data
    says. Writing each one down explicitly is what makes the comparison
    checkable -- and what makes a wrong claim visible as a large difference
    rather than as a quietly missing row.
    """

    label: str
    instance: str
    city_dataset: str
    city_metric: str
    library_dataset: str
    city_filters: dict[str, str] = field(default_factory=dict)
    library_filters: dict[str, str] = field(default_factory=dict)
    note: str = ''


def _select(df: pl.DataFrame, filters: dict[str, str]) -> pl.DataFrame:
    """Apply equality filters, ignoring any column the frame does not carry."""
    out = df
    for column, value in filters.items():
        if column not in out.columns:
            continue
        out = out.filter(pl.col(column).cast(pl.String).str.to_lowercase() == value.lower())
    return out


STRUCTURAL_COLUMNS = frozenset({'dataset', 'metric', 'quantity', 'unit', 'year', 'value', 'source', 'comment'})
"""Columns that are not dimensions; anything else left varying makes a series ambiguous."""


class AmbiguousSeriesError(ValueError):
    """
    A mapping did not reduce one side to a single series.

    Raised rather than taking the first row. Sedona's grid factor varies by
    ``electricity_user`` -- its wastewater plant is charged zero in 2023 and 2024
    -- so silently picking one would compare the library against an arbitrary one
    of several different city values and report agreement or disagreement that
    depends on row order.
    """


def _series(
    df: pl.DataFrame,
    dataset: str | None,
    metric: str | None,
    filters: dict[str, str],
    side: str,
) -> pl.DataFrame:
    """Reduce a long frame to a single (year, value, unit) series, or say why it cannot."""
    out = df
    if dataset is not None and 'dataset' in out.columns:
        out = out.filter(pl.col('dataset') == dataset)
    if metric is not None and 'metric' in out.columns:
        out = out.filter(pl.col('metric') == metric)
    out = _select(out, filters)

    if not out.is_empty():
        varying = [
            column
            for column in out.columns
            if column not in STRUCTURAL_COLUMNS and out[column].n_unique() > 1
        ]
        if varying:
            detail = '; '.join(
                f'{c}={sorted(str(v) for v in out[c].unique().to_list())[:6]}' for c in varying
            )
            raise AmbiguousSeriesError(
                f'The {side} side still varies over {varying} after filtering, so it is not one '
                f'series. Add a filter for each. Values seen: {detail}'
            )
        duplicated = out.group_by('year').len().filter(pl.col('len') > 1)
        if not duplicated.is_empty():
            raise AmbiguousSeriesError(
                f'The {side} side has more than one value for year(s) '
                f'{sorted(duplicated["year"].to_list())} with no dimension distinguishing them.'
            )

    keep = [c for c in ('year', 'value', 'unit') if c in out.columns]
    return out.select(keep).sort('year')


def compare_one(
    library: pl.DataFrame,
    city: pl.DataFrame,
    mapping: FactorMapping,
    tolerance: float = DEFAULT_TOLERANCE,
) -> pl.DataFrame:
    """Compare one mapped pair, year by year."""
    lib = _series(library, mapping.library_dataset, None, mapping.library_filters, 'library')
    cty = _series(city, mapping.city_dataset, mapping.city_metric, mapping.city_filters, 'city')

    joined = cty.join(lib, on='year', how='full', suffix='_lib', coalesce=True).sort('year')

    rows: list[dict[str, object]] = []
    for row in joined.iter_rows(named=True):
        city_value, lib_value = row.get('value'), row.get('value_lib')
        city_unit, lib_unit = row.get('unit'), row.get('unit_lib')

        converted: float | None = None
        verdict = Verdict.AGREES
        difference: float | None = None
        relative: float | None = None

        if city_value is None:
            verdict = Verdict.LIBRARY_ONLY
        elif lib_value is None:
            verdict = Verdict.CITY_ONLY
        else:
            try:
                converted = convert(float(lib_value), str(lib_unit), str(city_unit))
            except (pint.DimensionalityError, pint.UndefinedUnitError):
                verdict = Verdict.INCOMPARABLE
            else:
                difference = converted - float(city_value)
                denominator = abs(float(city_value))
                relative = abs(difference) / denominator if denominator else (0.0 if not difference else float('inf'))
                verdict = Verdict.AGREES if relative <= tolerance else Verdict.DIFFERS

        rows.append({
            'label': mapping.label,
            'instance': mapping.instance,
            'year': row['year'],
            'city_value': city_value,
            'city_unit': city_unit,
            'library_value': lib_value,
            'library_unit': lib_unit,
            'library_in_city_unit': converted,
            'difference': difference,
            'relative_difference': relative,
            'verdict': verdict,
        })

    if not rows:
        return pl.DataFrame(schema=REPORT_SCHEMA)
    return pl.DataFrame(rows, schema_overrides=REPORT_SCHEMA)


REPORT_SCHEMA: dict[str, pl.DataType] = {
    'label': pl.String,
    'instance': pl.String,
    'year': pl.Int32,
    'city_value': pl.Float64,
    'city_unit': pl.String,
    'library_value': pl.Float64,
    'library_unit': pl.String,
    'library_in_city_unit': pl.Float64,
    'difference': pl.Float64,
    'relative_difference': pl.Float64,
    'verdict': pl.String,
}


def compare_all(
    library: pl.DataFrame,
    city_frames: dict[str, pl.DataFrame],
    mappings: list[FactorMapping],
    tolerance: float = DEFAULT_TOLERANCE,
) -> pl.DataFrame:
    """
    Compare every mapping whose city frame is available.

    ``city_frames`` is keyed by instance. A mapping whose instance has not been
    exported is skipped rather than reported as a mismatch: not having looked is
    a different thing from having looked and found nothing.
    """
    frames = [
        compare_one(library, city_frames[m.instance], m, tolerance)
        for m in mappings
        if m.instance in city_frames
    ]
    if not frames:
        return pl.DataFrame(schema=REPORT_SCHEMA)
    return pl.concat(frames, how='vertical')


def summarise(report: pl.DataFrame) -> pl.DataFrame:
    """Count outcomes per series, worst first."""
    if report.is_empty():
        return pl.DataFrame(schema={'label': pl.String, 'verdict': pl.String, 'n': pl.UInt32})
    order = {
        Verdict.DIFFERS: 0,
        Verdict.INCOMPARABLE: 1,
        Verdict.CITY_ONLY: 2,
        Verdict.LIBRARY_ONLY: 3,
        Verdict.AGREES: 4,
    }
    return (
        report.group_by('label', 'verdict')
        .len(name='n')
        .with_columns(pl.col('verdict').replace_strict(order, default=9).alias('_order'))
        .sort(['_order', 'label'])
        .drop('_order')
    )


def format_report(report: pl.DataFrame) -> str:
    """Render the comparison as plain text, leading with what disagrees."""
    if report.is_empty():
        return 'Nothing compared: no mapping matched both a library table and a city export.'

    lines = ['Library vs. city factors', '=' * 78]

    problems = report.filter(pl.col('verdict') != Verdict.AGREES)
    if problems.is_empty():
        lines.append('\nEvery compared factor agrees with the library within tolerance.')
    else:
        lines.append('\nDisagreements and gaps')
        lines.append('-' * 78)
        for row in problems.sort(['verdict', 'label', 'year']).iter_rows(named=True):
            detail = ''
            if row['verdict'] == Verdict.DIFFERS:
                detail = (
                    f"city {row['city_value']:.6g} vs library {row['library_in_city_unit']:.6g} "
                    f"{row['city_unit']}  ({row['relative_difference'] * 100:.1f}%)"
                )
            elif row['verdict'] == Verdict.INCOMPARABLE:
                detail = f"{row['library_unit']} vs {row['city_unit']}"
            elif row['verdict'] == Verdict.CITY_ONLY:
                detail = f"city has {row['city_value']:.6g} {row['city_unit']}, library has no value"
            elif row['verdict'] == Verdict.LIBRARY_ONLY:
                detail = f"library has {row['library_value']:.6g} {row['library_unit']}, city has none"
            lines.append(f"  {row['label']:38} {row['year']}  {row['verdict']:18} {detail}")

    lines.append('')
    lines.append('Summary')
    lines.append('-' * 78)
    lines.extend(
        f"  {row['label']:38} {row['verdict']:18} {row['n']}"
        for row in summarise(report).iter_rows(named=True)
    )
    return '\n'.join(lines)
