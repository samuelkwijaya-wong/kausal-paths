r"""
Compare the library's factors against what the US city models already use.

    # 1. build the library (needs network; see README)
    python -m tools.us_factors.build_csv --all

    # 2. export the city datasets you want to check
    python manage.py export_dataset sedona sedona/grid_emission_factors \
        --out /tmp/city-exports --format wide

    # 3. compare
    python -m tools.us_factors.compare_to_cities --city-dir /tmp/city-exports

Every CSV under ``--city-dir`` is read and attributed to an instance by the
namespace of its ``Dataset`` column, so exports for several cities can sit in one
directory.

This changes nothing. It is a report, and its job is to answer the question that
decides whether the library is adoptable: where do the shared factors agree with
what the cities already compute, and where do they not?
"""

import argparse
import sys
from pathlib import Path

import polars as pl

from tools.us_factors import city_factors
from tools.us_factors.build_csv import TABLES_DIR
from tools.us_factors.compare import (
    DEFAULT_TOLERANCE,
    AmbiguousSeriesError,
    compare_one,
    format_report,
)
from tools.us_factors.tidy import LONG_SCHEMA


def to_long(wide: pl.DataFrame) -> pl.DataFrame:
    """
    Turn a wide CSV (year columns) back into the long frame the comparison uses.

    Accepts both the library's own output and the wide export produced by
    ``manage.py export_dataset``, which share the format.
    """
    renames = {c: c.lower() for c in wide.columns if c.lower() in LONG_SCHEMA}
    df = wide.rename(renames)
    year_cols = [c for c in df.columns if c.isdigit()]
    if not year_cols:
        raise ValueError(f'No year columns found; got {df.columns}')
    id_cols = [c for c in df.columns if c not in year_cols]
    long = df.unpivot(on=year_cols, index=id_cols, variable_name='year', value_name='value')
    return (
        long.with_columns(
            pl.col('year').cast(pl.Int32),
            pl.col('value').cast(pl.Float64, strict=False),
        )
        .drop_nulls('value')
    )


def load_dir(directory: Path) -> list[pl.DataFrame]:
    """Read every CSV in a directory as a long frame."""
    frames = []
    for path in sorted(directory.glob('*.csv')):
        try:
            frames.append(to_long(pl.read_csv(path, infer_schema_length=2000)))
        except (ValueError, pl.exceptions.PolarsError) as exc:  # noqa: PERF203 - a directory of files, not a hot loop
            # One unreadable export must not stop the rest being compared, and a
            # skipped file is named rather than dropped silently.
            print(f'  skipped {path.name}: {exc}', file=sys.stderr)
    return frames


def group_by_instance(frames: list[pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """
    Attribute each city frame to an instance by its dataset namespace.

    ``sedona/grid_emission_factors`` belongs to ``sedona``. That convention is
    what makes a directory of mixed exports usable without further declaration.
    """
    out: dict[str, list[pl.DataFrame]] = {}
    for frame in frames:
        if 'dataset' not in frame.columns:
            continue
        for dataset in frame['dataset'].unique().to_list():
            if not dataset or '/' not in str(dataset):
                continue
            instance = str(dataset).split('/', 1)[0]
            out.setdefault(instance, []).append(frame.filter(pl.col('dataset') == dataset))
    return {k: pl.concat(v, how='diagonal') for k, v in out.items()}


def _print_unresolved(empty: list[str], ambiguous: list[str]) -> None:
    """
    Report the mappings that produced no comparison, and why.

    Without this a mapping whose dataset was never exported, or whose category
    ids do not match, contributes nothing and looks exactly like agreement. The
    quiet cases are the ones worth naming.
    """
    if ambiguous:
        print('\nMappings needing another filter')
        print('-' * 78)
        for line in ambiguous:
            print(f'  {line}')
    if empty:
        print('\nMappings that matched nothing on one or both sides')
        print('-' * 78)
        for label in empty:
            print(f'  {label}')
        print(
            '  (the dataset was not in the export, the library table is not built, '
            'or the\n   dimension category ids differ -- not evidence of agreement)'
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='python -m tools.us_factors.compare_to_cities',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--city-dir', type=Path, required=True, help='Directory of exported city CSVs.')
    parser.add_argument('--tables-dir', type=Path, default=TABLES_DIR, help='Library tables directory.')
    parser.add_argument('--instance', action='append', default=None, help='Limit to an instance (repeatable).')
    parser.add_argument('--tolerance', type=float, default=DEFAULT_TOLERANCE,
                        help=f'Relative difference counted as agreement (default {DEFAULT_TOLERANCE}).')
    parser.add_argument('--csv', type=Path, default=None, help='Also write the full report here.')
    args = parser.parse_args(argv)

    library_frames = load_dir(args.tables_dir)
    if not library_frames:
        print(
            f'No library tables in {args.tables_dir}.\n'
            'Build them first: python -m tools.us_factors.build_csv --all',
            file=sys.stderr,
        )
        return 2
    library = pl.concat(library_frames, how='diagonal')

    if not args.city_dir.is_dir():
        print(f'--city-dir {args.city_dir} is not a directory', file=sys.stderr)
        return 2
    cities = group_by_instance(load_dir(args.city_dir))
    if not cities:
        print(f'No usable city exports in {args.city_dir}', file=sys.stderr)
        return 2
    print(f'Loaded city exports for: {", ".join(sorted(cities))}\n')

    mappings = city_factors.for_instances(set(args.instance) if args.instance else None)

    reports = []
    empty: list[str] = []
    ambiguous: list[str] = []
    for mapping in mappings:
        if mapping.instance not in cities:
            continue
        try:
            result = compare_one(library, cities[mapping.instance], mapping, args.tolerance)
        except AmbiguousSeriesError as exc:
            # Not a failure of the run: it is the comparison saying the mapping is
            # underspecified, and naming what to add. Report and carry on.
            ambiguous.append(f'{mapping.label}: {exc}')
            continue
        if result.is_empty():
            empty.append(mapping.label)
        else:
            reports.append(result)

    if not reports:
        print('Nothing compared.', file=sys.stderr)
        _print_unresolved(empty, ambiguous)
        return 1

    report = pl.concat(reports, how='vertical')
    print(format_report(report))
    _print_unresolved(empty, ambiguous)

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        report.write_csv(args.csv)
        print(f'\nFull report written to {args.csv}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
