"""
Run the banff-demo model locally from the CSVs, without DVC, and reconcile it.

Builds each dataset exactly as `tools/upload_new_dataset.py` would before pushing it
(`build_dvc_frame`), hands the frames to the model in place of the DVC repository, then
computes the three scenarios and checks them against the Roadmap's published totals.

Run from the repository root (needs a working Paths development environment):

    python configs/banff-demo/check_banff_demo.py [--write RECONCILIATION.md]

Exits non-zero if any check fails.
"""

# ruff: noqa: INP001, C901, PLR0912, PLR0915, E501, ISC004  # a standalone check script, run directly

import argparse
import sys
from pathlib import Path

from kausal_common.development.django import init_django

init_django()

import dvc_pandas  # noqa: E402
import polars as pl  # noqa: E402
from dvc_pandas import DatasetMeta  # noqa: E402

from nodes.constants import FORECAST_COLUMN, VALUE_COLUMN, YEAR_COLUMN  # noqa: E402
from nodes.context import Context  # noqa: E402
from nodes.instance_loader import InstanceLoader  # noqa: E402
from tools.upload_new_dataset import build_dvc_frame, load_data, split_by_dataset, to_snake_case  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
NAMESPACE = 'banff-demo'

PUBLISHED = {
    2016: 425080,
    ('business_as_usual', 2050): 292160,
    ('default', 2050): 71884,
}
ROADMAP_2050 = {
    'energy_production': 956,
    'fugitive': 2044,
    'residential': 11324,
    'waste': 4876,
    'commercial': 19408,
    'institutional': 1939,
    'municipal': 855,
    'local_transport': 4382,
    'visitor_transport': 26100,
}
BAU_2050 = {
    'energy_production': 0,
    'fugitive': 6658,
    'residential': 26882,
    'waste': 16821,
    'commercial': 60104,
    'institutional': 6004,
    'municipal': 2647,
    'local_transport': 22381,
    'visitor_transport': 150664,
}
ACTION_2050 = {  # p. ix, t
    'electrify_visitor_vehicles': 64310,
    'enhanced_transit': 27920,
    'non_residential_retrofits': 19040,
    'gas_cogeneration': 16430,
    'renewable_electricity_procurement': 15890,
}
TOLERANCE_T = 5


def build_datasets(csv_path: Path, keep_empty: bool) -> dict[str, dvc_pandas.Dataset]:
    full = load_data(str(csv_path), ',', 'utf-8')
    out = {}
    for name, df in split_by_dataset(full).items():
        frame, units, _metrics, _desc = build_dvc_frame(df, 'en', None, keep_empty_cells=keep_empty, verbose=False)
        identifier = f'{NAMESPACE}/{to_snake_case(name)}'
        index_columns = [c for c in frame.columns if c not in units and c.lower() not in ('source', 'comment')]
        meta = DatasetMeta(identifier=identifier, index_columns=index_columns, units=units, metadata={'name': {'en': name}})
        out[identifier] = dvc_pandas.Dataset(frame, meta=meta)
    return out


def install(datasets: dict[str, dvc_pandas.Dataset]) -> None:
    def load_dvc_dataset(self: Context, ds_id: str) -> dvc_pandas.Dataset:
        if ds_id not in datasets:
            raise KeyError(f'Dataset {ds_id} is not in the local CSVs')
        return datasets[ds_id]

    Context.load_dvc_dataset = load_dvc_dataset  # type: ignore[method-assign]
    Context.load_all_dvc_datasets = lambda _self: None  # type: ignore[method-assign]
    Context.warm_dvc_cache = lambda _self: None  # type: ignore[method-assign]


def series(ctx: Context, node_id: str, by: str | None = None) -> pl.DataFrame:
    df = ctx.get_node(node_id).get_output_pl()
    keys = [YEAR_COLUMN] + ([by] if by else [])
    col = df.metric_cols[0] if VALUE_COLUMN not in df.columns else VALUE_COLUMN
    return pl.DataFrame(df).group_by(keys).agg(pl.col(col).sum().alias('value'), pl.col(FORECAST_COLUMN).first()).sort(keys)


def at(df: pl.DataFrame, year: int, **filt) -> float:
    q = df.filter(pl.col(YEAR_COLUMN) == year)
    for k, v in filt.items():
        q = q.filter(pl.col(k) == v)
    return float(q['value'].sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', help='write a markdown reconciliation report to this path')
    args = ap.parse_args()

    datasets = build_datasets(HERE / 'banff_demo_data.csv', keep_empty=False)
    install(datasets)
    loader = InstanceLoader.from_yaml(ROOT / 'configs' / 'banff-demo.yaml')
    ctx = loader.context
    ctx.cache.clear()

    lines: list[str] = []
    failures: list[str] = []

    def check(label: str, got: float, want: float, tol: float = TOLERANCE_T) -> None:
        ok = abs(got - want) <= tol
        lines.append(f'| {label} | {want:,.0f} | {got:,.0f} | {got - want:+,.0f} | {"OK" if ok else "FAIL"} |')
        if not ok:
            failures.append(label)

    # Every node must compute in every scenario, not only the ones the checks below read.
    for scen_id in ('baseline', 'business_as_usual', 'default'):
        with ctx.get_scenario(scen_id).override(set_active=True, isolated=True):
            for node in ctx.nodes.values():
                try:
                    node.get_output_pl()
                except Exception as e:
                    failures.append(f'{node.id} does not compute in {scen_id}: {e}')
    rp = series(ctx, 'roadmap_published_emissions')
    lines += [
        f'Roadmap 2050 as published (node): {at(rp, 2050):,.0f} t; years in node: {sorted(rp[YEAR_COLUMN].unique().to_list())}.',
        '',
    ]

    results: dict[str, pl.DataFrame] = {}
    for scen_id in ('baseline', 'business_as_usual', 'default'):
        scen = ctx.get_scenario(scen_id)
        with scen.override(set_active=True, isolated=True):
            results[scen_id] = series(ctx, 'net_emissions', 'sector')
            if scen_id == 'default':
                eff = {
                    n: series(ctx, n)
                    for n in (
                        'emissions_per_resident',
                        'emissions_per_visitor_adjusted_person',
                        'visitor_transport_emissions_per_visit',
                    )
                }
                action_impacts = {}
                for a in ACTION_2050:
                    act = ctx.get_action(a)
                    act.enabled_param.set(False)
                    without = series(ctx, 'net_emissions')
                    act.enabled_param.set(True)
                    action_impacts[a] = at(without, 2050) - at(results['default'], 2050)

    lines += ['## Totals', '', '| Check | Published | Model | Difference | Result |', '|---|---:|---:|---:|---|']
    check('2016 inventory total', at(results['default'], 2016), PUBLISHED[2016])
    check('Business as usual 2050 total', at(results['business_as_usual'], 2050), PUBLISHED[('business_as_usual', 2050)])
    check('Roadmap 2050 total', at(results['default'], 2050), PUBLISHED[('default', 2050)])
    check(
        'Actions total in 2050 (BAU minus Roadmap)',
        at(results['business_as_usual'], 2050) - at(results['default'], 2050),
        220280,
    )
    check('Baseline (no change) 2050 equals 2016', at(results['baseline'], 2050), PUBLISHED[2016])

    lines += ['', '## By sector, 2050', '', '| Check | Published | Model | Difference | Result |', '|---|---:|---:|---:|---|']
    for s, v in BAU_2050.items():
        check(f'BAU 2050, {s}', at(results['business_as_usual'], 2050, sector=s), v, 1)
    for s, v in ROADMAP_2050.items():
        check(f'Roadmap 2050, {s}', at(results['default'], 2050, sector=s), v, 1)

    lines += [
        '',
        '## The five modelled actions, effect in 2050 (switching each off in the Roadmap scenario)',
        '',
        '| Check | Published | Model | Difference | Result |',
        '|---|---:|---:|---:|---|',
    ]
    for a, v in ACTION_2050.items():
        check(f'{a}', action_impacts[a], v, 1)

    lines += ['', '## Path, total t CO2e', '', '| Year | No change | Business as usual | Roadmap |', '|---|---:|---:|---:|']
    for y in (2016, 2020, 2025, 2026, 2030, 2031, 2035, 2040, 2045, 2050):
        lines.append(
            f'| {y} | {at(results["baseline"], y):,.0f} | {at(results["business_as_usual"], y):,.0f} | {at(results["default"], y):,.0f} |'
        )
    lines += [
        '',
        '## Efficiency measures, Roadmap scenario',
        '',
        '| Year | t per resident | t per visitor-adjusted person | kg per visit (visitor transport) |',
        '|---|---:|---:|---:|',
    ]
    for y in (2016, 2026, 2030, 2050):
        lines.append(
            f'| {y} | {at(eff["emissions_per_resident"], y):.1f} | {at(eff["emissions_per_visitor_adjusted_person"], y):.1f}'
            f' | {at(eff["visitor_transport_emissions_per_visit"], y):.1f} |'
        )

    rec = series(ctx, 'inventory_reconciliation_emissions', 'sector')
    bau = results['business_as_usual']
    lines += [
        '',
        "## 2026 placeholder against the model's business as usual in 2026",
        '',
        '| Check | Model BAU 2026 | Placeholder 2026 | Difference | Result |',
        '|---|---:|---:|---:|---|',
    ]
    for s in BAU_2050:
        check(f'2026 placeholder, {s}', at(rec, 2026, sector=s), at(bau, 2026, sector=s), 1)
    vap = series(ctx, 'visitor_adjusted_population')
    lines += [
        '',
        '## Visitor-adjusted population',
        '',
        '| Check | Published | Model | Difference | Result |',
        '|---|---:|---:|---:|---|',
    ]
    for y, v in ((2016, 23920), (2021, 25015), (2026, 26154), (2031, 27388), (2050, 33400)):
        check(f'Visitor-adjusted population {y}', at(vap, y), v, 50)
    gef = series(ctx, 'grid_emission_factor_total')
    lines += [
        '',
        f'Grid factor, g CO2e/kWh: 2016 {at(gef, 2016):.1f}, 2026 {at(gef, 2026):.1f}, 2031 {at(gef, 2031):.1f}, 2050 {at(gef, 2050):.1f}.',
    ]

    header = [
        '# Banff demo - reconciliation check',
        '',
        'Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap.'
        ' Not prepared or endorsed by the Town of Banff.',
        '',
        'Written by `configs/banff-demo/check_banff_demo.py`, which runs the model from the dataset CSVs and'
        " compares it with the Roadmap's published figures. Tolerance is 5 t for totals and 1 t for sectors."
        ' The 2016 and BAU 2050 totals are 1 t off because the published sector values themselves sum to'
        ' 425,079 and 292,161; the action total is 3 t under the printed 220.28 kt for the same reason.',
        '',
    ]
    report = '\n'.join(header + lines)
    print(report)
    if args.write:
        Path(args.write).write_text(report + '\n', encoding='utf-8')
    if failures:
        print('\nFAILED:', ', '.join(failures))
        return 1
    print('\nAll checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
