"""
River-flood adaptation demo: CLIMADA numbers for a Kausal Paths model.

This script is a stand-alone program. It runs in its own Python environment
(CLIMADA needs Python < 3.14, Kausal Paths needs >= 3.14) and is never imported
by Kausal Paths. See README.md in this folder.

What it does:

1. Invents a small city ("Riverford") on a 30 x 30 grid of 100 m cells with a
   river along one edge, three districts and two kinds of buildings.
2. Invents a set of river-flood events for today (2025) and for 2050.
3. Asks CLIMADA for the expected annual flood damage per district, without
   measures, with each adaptation measure alone, and with all of them.
4. Draws a straight line between 2025 and 2050 to get yearly values.
5. Writes result tables (CSV) and a data file that Kausal Paths can load.

The city, the floods and the building values are INVENTED. The damage curves
are the published JRC curves for Europe (Huizinga et al. 2017), and the damage
arithmetic is CLIMADA's.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from climada.engine import ImpactCalc
from climada.entity import Exposures, ImpactFunc, ImpactFuncSet, Measure
from climada.hazard import Centroids, Hazard
from scipy import sparse

HERE = Path(__file__).resolve().parent
DEFAULT_PATHS_MODULE = HERE.parent.parent / 'configs' / 'modules' / 'riverford' / 'climada_results.yaml'

HAZ_TYPE = 'RF'  # CLIMADA's code for river flood

# --- The invented city -------------------------------------------------------

N_ROWS = 30  # rows run away from the river; row 0 is on the river bank
N_COLS = 30  # columns run along the river
CELL_M = 100.0
ORIGIN_LAT, ORIGIN_LON = 50.0, 8.0  # arbitrary; only used to give cells coordinates

DISTRICTS = {1: 'riverside', 2: 'old_town', 3: 'harbour'}
DISTRICT_NAMES = {'riverside': 'Riverside', 'old_town': 'Old Town', 'harbour': 'Harbour'}
DISTRICT_IDS = {name: rid for rid, name in DISTRICTS.items()}

RIVER_ROWS = 10  # Riverside and the Harbour take the 10 rows nearest the river
HARBOUR_FIRST_COL = 20  # the Harbour takes the last 10 columns of those rows

IMPF_RESIDENTIAL, IMPF_INDUSTRIAL = 1, 2
VALUE_PER_CELL_MEUR = {'riverside': 12.0, 'old_town': 18.0, 'harbour': 20.0}

# Ground height above the normal river level, in metres
GROUND_AT_BANK_M = 1.3
GROUND_RISE_PER_ROW_M = 0.13
HARBOUR_LOWER_BY_M = 0.2

# --- The invented floods -----------------------------------------------------

N_EVENTS = 1000  # one yearly peak river level for each of 1000 imagined years
STAGE_LOC_M, STAGE_SCALE_M = 0.2, 0.45  # Gumbel distribution of the yearly peak

YEAR_PRESENT, YEAR_FUTURE = 2025, 2050
FIRST_SHOWN_YEAR = 2020  # 2020-2025 are shown flat at the present-day level
STAGE_RISE_BY_FUTURE_M = 0.25  # climate change: higher flood peaks by 2050
VALUE_GROWTH_BY_FUTURE = 1.2  # economic growth: more value at risk by 2050

# --- Published damage curves -------------------------------------------------
# JRC global flood depth-damage functions, Europe (Huizinga, de Moel & Szewczyk
# 2017, doi:10.2760/16510), as tabulated in climada_petals v6.2.0
# (climada_petals/entity/impact_funcs/river_flood.py).
JRC_DEPTH_M = [0, 0.05, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 12]
JRC_DAMAGE = {
    IMPF_RESIDENTIAL: [0, 0, 0.25, 0.4, 0.5, 0.6, 0.75, 0.85, 0.95, 1, 1],
    IMPF_INDUSTRIAL: [0, 0, 0.15, 0.27, 0.4, 0.52, 0.7, 0.85, 1, 1, 1],
}

DISCOUNT_RATE_FOR_REPORT = 0.03


@dataclass
class MeasureSpec:
    id: str
    name: str
    group: str
    description: str
    climada: dict
    investment_meur: float
    construction_years: tuple[int, int]
    maintenance_meur_per_year: float

    @property
    def operational_from(self) -> int:
        return self.construction_years[1] + 1


@dataclass
class State:
    """Everything CLIMADA needs for one year: assets, floods, damage curves."""

    year: int
    exposures: Exposures
    hazard: Hazard
    impfs: ImpactFuncSet


def load_measures(path: Path) -> list[MeasureSpec]:
    raw = yaml.safe_load(path.read_text())
    return [
        MeasureSpec(
            id=m['id'],
            name=m['name'],
            group=m['group'],
            description=' '.join(m['description'].split()),
            climada=m['climada'],
            investment_meur=float(m['investment_meur']),
            construction_years=(int(m['construction_years'][0]), int(m['construction_years'][1])),
            maintenance_meur_per_year=float(m['maintenance_meur_per_year']),
        )
        for m in raw['measures']
    ]


# --- Building the city -------------------------------------------------------


def grid() -> pd.DataFrame:
    """One row per 100 m cell: position, district, ground height, building type."""
    rows, cols = np.meshgrid(np.arange(N_ROWS), np.arange(N_COLS), indexing='ij')
    rows, cols = rows.ravel(), cols.ravel()
    lat = ORIGIN_LAT + rows * CELL_M / 111_320.0
    lon = ORIGIN_LON + cols * CELL_M / (111_320.0 * np.cos(np.radians(ORIGIN_LAT)))

    near_river = rows < RIVER_ROWS
    harbour = near_river & (cols >= HARBOUR_FIRST_COL)
    region_id = np.where(
        harbour, DISTRICT_IDS['harbour'], np.where(near_river, DISTRICT_IDS['riverside'], DISTRICT_IDS['old_town'])
    )
    ground = GROUND_AT_BANK_M + GROUND_RISE_PER_ROW_M * rows - np.where(harbour, HARBOUR_LOWER_BY_M, 0.0)
    value = np.array([VALUE_PER_CELL_MEUR[DISTRICTS[r]] for r in region_id]) * 1e6

    return pd.DataFrame({
        'row': rows,
        'col': cols,
        'latitude': lat,
        'longitude': lon,
        'region_id': region_id,
        'ground_m': ground,
        'value': value,
        f'impf_{HAZ_TYPE}': np.where(harbour, IMPF_INDUSTRIAL, IMPF_RESIDENTIAL),
    })


def make_exposures(cells: pd.DataFrame, value_factor: float, year: int) -> Exposures:
    exp = Exposures(
        data={
            'value': cells['value'].to_numpy() * value_factor,
            'region_id': cells['region_id'].to_numpy(),
            f'impf_{HAZ_TYPE}': cells[f'impf_{HAZ_TYPE}'].to_numpy(),
        },
        lat=cells['latitude'].to_numpy(),
        lon=cells['longitude'].to_numpy(),
        crs='EPSG:4326',
        ref_year=year,
        value_unit='EUR',
    )
    exp.check()
    return exp


def make_hazard(cells: pd.DataFrame, stages_m: np.ndarray) -> Hazard:
    """Flood depth in every cell for every event: river level minus ground height."""
    depth = np.clip(stages_m[:, None] - cells['ground_m'].to_numpy()[None, :], 0.0, None)
    n_events = len(stages_m)
    haz = Hazard(
        haz_type=HAZ_TYPE,
        units='m',
        centroids=Centroids(lat=cells['latitude'].to_numpy(), lon=cells['longitude'].to_numpy(), crs='EPSG:4326'),
        event_id=np.arange(1, n_events + 1),
        event_name=[f'flood_{i}' for i in range(1, n_events + 1)],
        date=np.full(n_events, datetime(2025, 1, 1, tzinfo=UTC).toordinal()),
        orig=np.zeros(n_events, dtype=bool),
        frequency=np.full(n_events, 1.0 / n_events),
        intensity=sparse.csr_matrix(depth),
        fraction=sparse.csr_matrix(depth.shape),
    )
    haz.check()
    return haz


def make_impfs() -> ImpactFuncSet:
    names = {IMPF_RESIDENTIAL: 'JRC Europe residential', IMPF_INDUSTRIAL: 'JRC Europe industrial'}
    return ImpactFuncSet([
        ImpactFunc(
            haz_type=HAZ_TYPE,
            id=impf_id,
            name=names[impf_id],
            intensity=np.array(JRC_DEPTH_M, dtype=float),
            mdd=np.array(damage, dtype=float),
            paa=np.ones(len(JRC_DEPTH_M)),
            intensity_unit='m',
        )
        for impf_id, damage in JRC_DAMAGE.items()
    ])


def make_states(cells: pd.DataFrame, seed: int) -> dict[int, State]:
    rng = np.random.default_rng(seed)
    stages = rng.gumbel(STAGE_LOC_M, STAGE_SCALE_M, N_EVENTS)
    return {
        YEAR_PRESENT: State(YEAR_PRESENT, make_exposures(cells, 1.0, YEAR_PRESENT), make_hazard(cells, stages), make_impfs()),
        YEAR_FUTURE: State(
            YEAR_FUTURE,
            make_exposures(cells, VALUE_GROWTH_BY_FUTURE, YEAR_FUTURE),
            make_hazard(cells, stages + STAGE_RISE_BY_FUTURE_M),
            make_impfs(),
        ),
    }


# --- Measures ----------------------------------------------------------------


def relocated_exposures(cells: pd.DataFrame, exposures: Exposures, rows_to_clear: list[int]) -> Exposures:
    """Move the value of the lowest Riverside rows to the highest rows of the Old Town."""
    new_exp = exposures.copy(deep=True)
    values = new_exp.gdf['value'].to_numpy().copy()
    leaving = (cells['region_id'] == DISTRICT_IDS['riverside']) & cells['row'].isin(rows_to_clear)
    receiving = cells['row'] >= N_ROWS - len(rows_to_clear)
    moved = values[leaving.to_numpy()].sum()
    values[leaving.to_numpy()] = 0.0
    values[receiving.to_numpy()] += moved / receiving.sum()
    new_exp.gdf['value'] = values
    return new_exp


def make_climada_measure(spec: MeasureSpec, cells: pd.DataFrame, state: State) -> Measure:
    settings = dict(spec.climada)
    kwargs: dict = {'name': spec.name, 'haz_type': HAZ_TYPE, 'cost': spec.investment_meur * 1e6}
    if 'exp_region_id' in settings:
        kwargs['exp_region_id'] = [DISTRICT_IDS[name] for name in settings.pop('exp_region_id')]
    if 'relocate_rows' in settings:
        kwargs['exposures_set'] = relocated_exposures(cells, state.exposures, settings.pop('relocate_rows'))
    for key in ('hazard_inten_imp', 'mdd_impact', 'paa_impact'):
        if key in settings:
            kwargs[key] = tuple(settings.pop(key))
    kwargs.update(settings)
    measure = Measure(**kwargs)
    measure.check()
    return measure


def damage_by_district(exposures: Exposures, impfs: ImpactFuncSet, hazard: Hazard) -> dict[str, float]:
    """Return the expected annual damage per district, in million EUR per year."""
    impact = ImpactCalc(exposures, impfs, hazard).impact(save_mat=False)
    regions = exposures.gdf['region_id'].to_numpy()
    return {name: float(impact.eai_exp[regions == rid].sum()) / 1e6 for rid, name in DISTRICTS.items()}


def run_climada(cells: pd.DataFrame, states: dict[int, State], specs: list[MeasureSpec]) -> pd.DataFrame:
    """
    Compute the expected annual damage for both years and every case.

    Cases: 'none', each measure alone, and 'all' (every measure applied in turn).
    """
    records = []
    for year, state in states.items():
        cases: dict[str, tuple[Exposures, ImpactFuncSet, Hazard]] = {'none': (state.exposures, state.impfs, state.hazard)}
        combined = (state.exposures, state.impfs, state.hazard)
        # Relocation swaps the whole asset table, so in the combined case it has to go first.
        ordered = sorted(specs, key=lambda s: 'relocate_rows' not in s.climada)
        for spec in specs:
            cases[spec.id] = make_climada_measure(spec, cells, state).apply(state.exposures, state.impfs, state.hazard)
        for spec in ordered:
            combined = make_climada_measure(spec, cells, state).apply(*combined)
        cases['all'] = combined
        for case, (exp, impfs, haz) in cases.items():
            for district, ead in damage_by_district(exp, impfs, haz).items():
                records.append({'year': year, 'case': case, 'district': district, 'ead_meur': ead})
    return pd.DataFrame.from_records(records)


# --- From two years to a yearly series --------------------------------------


def yearly(endpoints: pd.DataFrame, specs: list[MeasureSpec]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    years = np.arange(FIRST_SHOWN_YEAR, YEAR_FUTURE + 1)
    weight = np.clip((years - YEAR_PRESENT) / (YEAR_FUTURE - YEAR_PRESENT), 0.0, 1.0)

    def line(case: str, district: str) -> np.ndarray:
        sel = endpoints[(endpoints['case'] == case) & (endpoints['district'] == district)].set_index('year')['ead_meur']
        return sel[YEAR_PRESENT] + (sel[YEAR_FUTURE] - sel[YEAR_PRESENT]) * weight

    districts = list(DISTRICTS.values())
    base = {d: line('none', d) for d in districts}
    baseline = pd.concat([pd.DataFrame({'year': years, 'district': d, 'ead_meur': base[d]}) for d in districts])

    effects = []
    remaining_product = {d: np.ones(len(years)) for d in districts}
    for spec in specs:
        in_operation = years >= spec.operational_from
        for d in districts:
            with_measure = line(spec.id, d)
            share = np.where(base[d] > 0, 1.0 - with_measure / np.where(base[d] > 0, base[d], 1.0), 0.0)
            share = np.where(in_operation, share, 0.0)
            remaining_product[d] = remaining_product[d] * (1.0 - share)
            effects.append(
                pd.DataFrame({
                    'year': years,
                    'measure': spec.id,
                    'district': d,
                    'ead_with_measure_meur': np.where(in_operation, with_measure, base[d]),
                    'reduction_share': share,
                })
            )

    costs = []
    for spec in specs:
        first, last = spec.construction_years
        building = (years >= first) & (years <= last)
        costs.append(
            pd.DataFrame({
                'year': years,
                'measure': spec.id,
                'investment_meur': np.where(building, spec.investment_meur / (last - first + 1), 0.0),
                'maintenance_meur': np.where(years >= spec.operational_from, spec.maintenance_meur_per_year, 0.0),
            })
        )

    all_in_operation = years >= max(s.operational_from for s in specs)
    check = pd.DataFrame({
        'year': years,
        'ead_no_measures_meur': sum(base[d] for d in districts),
        'ead_all_measures_climada_meur': sum(line('all', d) for d in districts),
        'ead_all_measures_paths_rule_meur': sum(base[d] * remaining_product[d] for d in districts),
    })[all_in_operation]
    return baseline, pd.concat(effects), pd.concat(costs), check


# --- Checks ------------------------------------------------------------------


def sanity_checks(
    cells: pd.DataFrame, states: dict[int, State], endpoints: pd.DataFrame, effects: pd.DataFrame, check: pd.DataFrame
) -> list[str]:
    lines = []
    present = states[YEAR_PRESENT]
    total_value = present.exposures.gdf['value'].sum() / 1e6
    none = endpoints[endpoints['case'] == 'none'].groupby('year')['ead_meur'].sum()
    share = none[YEAR_PRESENT] / total_value
    assert 0.0005 <= share <= 0.02, f'baseline damage is {share:.3%} of asset value, outside the plausible range'
    lines.append(
        f'Asset value {total_value:,.0f} MEUR; expected damage today {none[YEAR_PRESENT]:.2f} MEUR/a ({share:.3%} of value)'
    )
    assert none[YEAR_FUTURE] > none[YEAR_PRESENT], 'damage should be higher in 2050 than today'
    lines.append(f'Expected damage in {YEAR_FUTURE} without measures: {none[YEAR_FUTURE]:.2f} MEUR/a')

    shares = effects['reduction_share']
    assert shares.between(-1e-9, 1 + 1e-9).all(), 'a reduction share is outside 0..1'
    dike_old_town = effects[(effects['measure'] == 'river_dike') & (effects['district'] == 'old_town')]['reduction_share']
    assert dike_old_town.abs().max() < 1e-9, 'the dike should not change damage in the Old Town'
    lines.append('All reduction shares are between 0 and 1; the dike has no effect in the Old Town')

    # One cell by hand: sum over events of frequency x value x damage share at that depth
    cell = int(cells.index[(cells['row'] == 2) & (cells['col'] == 5)][0])
    depths = present.hazard.intensity[:, cell].toarray().ravel()
    damage_share = np.interp(depths, JRC_DEPTH_M, JRC_DAMAGE[IMPF_RESIDENTIAL])
    by_hand = float((present.hazard.frequency * damage_share).sum() * cells.loc[cell, 'value'])
    by_climada = float(ImpactCalc(present.exposures, present.impfs, present.hazard).impact(save_mat=False).eai_exp[cell])
    assert abs(by_hand - by_climada) <= 1e-6 * max(by_hand, 1.0), f'hand check failed: {by_hand} vs {by_climada}'
    lines.append(f'Hand calculation for one cell matches CLIMADA ({by_climada / 1e6:.4f} MEUR/a)')

    last = check.iloc[-1]
    gap = last['ead_all_measures_paths_rule_meur'] / last['ead_all_measures_climada_meur'] - 1.0
    avoided_climada = last['ead_no_measures_meur'] - last['ead_all_measures_climada_meur']
    avoided_paths = last['ead_no_measures_meur'] - last['ead_all_measures_paths_rule_meur']
    lines.append(
        f'All measures together in {int(last["year"])}: remaining damage is {last["ead_all_measures_climada_meur"]:.2f} MEUR/a '
        f'in CLIMADA and {last["ead_all_measures_paths_rule_meur"]:.2f} MEUR/a with the Paths combination rule ({gap:+.0%}); '
        f'avoided damage is {avoided_climada:.2f} against {avoided_paths:.2f} MEUR/a '
        f'({avoided_paths / avoided_climada - 1.0:+.0%})'
    )
    return lines


def benefit_cost_report(effects: pd.DataFrame, costs: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Discounted avoided damage and cost per measure, each measure on its own."""
    base = baseline.groupby('year')['ead_meur'].sum()
    rows = []
    for measure, eff in effects.groupby('measure', sort=False):
        with_measure = eff.groupby('year')['ead_with_measure_meur'].sum()
        cost = costs[costs['measure'] == measure].set_index('year')
        discount = (1 + DISCOUNT_RATE_FOR_REPORT) ** -(base.index.to_numpy() - YEAR_PRESENT).clip(min=0)
        benefit = float(((base - with_measure) * discount).sum())
        spend = float(((cost['investment_meur'] + cost['maintenance_meur']) * discount).sum())
        rows.append({
            'measure': measure,
            'discounted_avoided_damage_meur': benefit,
            'discounted_cost_meur': spend,
            'benefit_cost_ratio': benefit / spend,
        })
    return pd.DataFrame(rows)


# --- Output ------------------------------------------------------------------


def series(years: np.ndarray, values: np.ndarray) -> tuple[str, str]:
    pairs = [(int(y), round(float(v), 6) + 0.0) for y, v in zip(years, values, strict=True)]
    hist = ', '.join(f'[{y}, {v}]' for y, v in pairs if y <= YEAR_PRESENT)
    fore = ', '.join(f'[{y}, {v}]' for y, v in pairs if y > YEAR_PRESENT)
    return f'[{hist}]', f'[{fore}]'


def quoted(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def data_node(node_id: str, name: str, quantity: str, unit: str, years, values, output: str, category: str | None) -> str:
    hist, fore = series(np.asarray(years), np.asarray(values))
    lines = [
        f'- id: {node_id}',
        f'  name: {quoted(name)}',
        '  type: simple.AdditiveNode',
        f'  quantity: {quantity}',
        f'  unit: {unit}',
        f'  historical_values: {hist}',
        f'  forecast_values: {fore}',
        '  output_nodes:',
        f'  - id: {output}',
    ]
    if category is not None:
        lines += ['    to_dimensions:', '    - id: district', f'      categories: [{category}]']
    return '\n'.join(lines)


def sum_node(node_id: str, name: str, quantity: str, unit: str, description: str) -> str:
    return '\n'.join([
        f'- id: {node_id}',
        f'  name: {quoted(name)}',
        f'  description: {quoted(description)}',
        '  type: simple.AdditiveNode',
        f'  quantity: {quantity}',
        f'  unit: {unit}',
        '  input_dimensions: [district]',
        '  output_dimensions: [district]',
    ])


def write_paths_module(
    path: Path, specs: list[MeasureSpec], baseline: pd.DataFrame, effects: pd.DataFrame, costs: pd.DataFrame
) -> None:
    """Write the numbers as Kausal Paths data nodes (one small node per yearly series)."""
    header = (
        '# GENERATED by notebooks/climada-flood-demo/run_climada_flood.py -- do not edit by hand.\n'
        '# Re-run that script to refresh these numbers. The city, floods and asset values are invented;\n'
        f'# the damage figures were computed with CLIMADA {version("climada")}.\n\nnodes:'
    )
    blocks = [header]
    districts = list(DISTRICTS.values())

    blocks.append(
        sum_node(
            'baseline_flood_damage',
            'Expected annual flood damage without measures',
            'currency',
            'MEUR/a',
            'Yearly average river-flood damage if nothing is done, by district. Computed with CLIMADA for an invented city.',
        )
    )
    for d in districts:
        s = baseline[baseline['district'] == d].set_index('year')['ead_meur']
        name = f'Flood damage without measures, {DISTRICT_NAMES[d]}'
        blocks.append(
            data_node(f'baseline_damage_{d}', name, 'currency', 'MEUR/a', s.index, s.to_numpy(), 'baseline_flood_damage', d)
        )

    for spec in specs:
        eff = effects[effects['measure'] == spec.id]
        blocks.append(
            sum_node(
                f'{spec.id}_reduction',
                f'Share of flood damage avoided: {spec.name}',
                'fraction',
                'dimensionless',
                'Share of expected flood damage this measure removes when used on its own, by district. Computed with CLIMADA.',
            )
        )
        for d in districts:
            s = eff[eff['district'] == d].set_index('year')['reduction_share']
            name = f'Damage avoided by {spec.name}, {DISTRICT_NAMES[d]}'
            blocks.append(
                data_node(
                    f'{spec.id}_reduction_{d}',
                    name,
                    'fraction',
                    'dimensionless',
                    s.index,
                    s.to_numpy(),
                    f'{spec.id}_reduction',
                    d,
                )
            )
        cost = costs[costs['measure'] == spec.id].set_index('year')
        for kind in ('investment', 'maintenance'):
            name = f'{kind.capitalize()} cost if built: {spec.name}'
            block = data_node(
                f'{spec.id}_{kind}',
                name,
                'currency',
                'MEUR/a',
                cost.index,
                cost[f'{kind}_meur'].to_numpy(),
                f'{kind}_costs',
                None,
            )
            blocks.append(block + f'\n    tags: [{spec.id}_cost]')

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n\n'.join(blocks) + '\n')


def write_upload_csv(path: Path, baseline: pd.DataFrame, effects: pd.DataFrame, costs: pd.DataFrame) -> None:
    """Write the same numbers as one long table, ready to become a proper Kausal dataset later."""
    parts = [
        baseline.assign(metric='flood_damage_without_measures', measure='', unit='MEUR/a').rename(columns={'ead_meur': 'value'}),
        effects.assign(metric='reduction_share', unit='dimensionless').rename(columns={'reduction_share': 'value'}),
        costs.assign(metric='investment', district='', unit='MEUR/a').rename(columns={'investment_meur': 'value'}),
        costs.assign(metric='maintenance', district='', unit='MEUR/a').rename(columns={'maintenance_meur': 'value'}),
    ]
    columns = ['metric', 'measure', 'district', 'unit', 'year', 'value']
    long = pd.concat([p[columns] for p in parts])
    wide = long.pivot_table(index=['metric', 'measure', 'district', 'unit'], columns='year', values='value').reset_index()
    wide.to_csv(path, index=False, float_format='%.6g')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--source', choices=['synthetic'], default='synthetic', help='where floods and assets come from')
    parser.add_argument('--seed', type=int, default=42, help='seed for the invented flood events')
    parser.add_argument('--measures', type=Path, default=HERE / 'measures.yaml')
    parser.add_argument('--out', type=Path, default=HERE / 'output')
    parser.add_argument('--paths-module', type=Path, default=DEFAULT_PATHS_MODULE)
    args = parser.parse_args()

    specs = load_measures(args.measures)
    cells = grid()
    states = make_states(cells, args.seed)
    endpoints = run_climada(cells, states, specs)
    baseline, effects, costs, check = yearly(endpoints, specs)
    report = sanity_checks(cells, states, endpoints, effects, check)
    bcr = benefit_cost_report(effects, costs, baseline)

    args.out.mkdir(parents=True, exist_ok=True)
    fmt = {'index': False, 'float_format': '%.6g'}
    endpoints.to_csv(args.out / 'climada_endpoints.csv', **fmt)
    baseline.to_csv(args.out / 'flood_damage_baseline.csv', **fmt)
    effects.to_csv(args.out / 'measure_effects.csv', **fmt)
    costs.to_csv(args.out / 'measure_costs.csv', **fmt)
    check.to_csv(args.out / 'combined_check.csv', **fmt)
    bcr.to_csv(args.out / 'benefit_cost_report.csv', **fmt)
    write_upload_csv(args.out / 'paths_upload_wide.csv', baseline, effects, costs)
    (args.out / 'run_metadata.json').write_text(
        json.dumps(
            {
                'climada_version': version('climada'),
                'source': args.source,
                'seed': args.seed,
                'events': N_EVENTS,
                'years': [YEAR_PRESENT, YEAR_FUTURE],
                'inputs_are_invented': True,
            },
            indent=2,
        )
        + '\n'
    )
    write_paths_module(args.paths_module, specs, baseline, effects, costs)

    print('\n'.join(report))
    print(
        f'\nEach measure on its own, {FIRST_SHOWN_YEAR}-{YEAR_FUTURE}, '
        f'discounted at {DISCOUNT_RATE_FOR_REPORT:.0%} to {YEAR_PRESENT}:'
    )
    print(bcr.to_string(index=False, float_format=lambda v: f'{v:,.2f}'))
    print(f'\nTables written to {args.out}')
    print(f'Kausal Paths data file written to {args.paths_module}')


if __name__ == '__main__':
    main()
