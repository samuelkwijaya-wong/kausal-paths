"""Compare the sandiego-region model against the Roadmap appendix figures."""
import os
import sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paths.settings')
import django

django.setup()

import polars as pl

from nodes.instance_loader import InstanceLoader

YEARS = (2022, 2035, 2045)
CATS = ['onroad_transportation', 'electricity', 'natural_gas', 'industrial', 'other_fuels', 'offroad', 'solid_waste',
        'aviation', 'water', 'marine', 'agriculture', 'wastewater', 'rail']
# EPIC targets (MMT): 2022 from Appendix B, LA-BAU from Appendix D detail tables
TARGET = {
    'onroad_transportation': (10.08, 5.81, 2.37), 'electricity': (4.03, 0.85, 0.44), 'natural_gas': (3.01, 3.02, 3.01),
    'industrial': (2.40, 2.54, 2.72), 'other_fuels': (0.86, 0.87, 1.00), 'offroad': (0.68, 0.68, 0.68),
    'solid_waste': (0.32, 0.08, 0.08), 'aviation': (0.31, 0.43, 0.45), 'water': (0.25, 0.05, 0.00),
    'marine': (0.20, 0.24, 0.27), 'agriculture': (0.18, 0.20, 0.20), 'wastewater': (0.05, 0.05, 0.05), 'rail': (0.03, 0.01, 0.00),
}
MEASURES = {  # Appendix E standalone estimates (t)
    't1_public_transit': (193400, 153600), 't2_active_transportation': (124300, 64600), 't3_flexible_fleets': (136400, 53300),
    't4_transportation_demand_management': (59200, 47500), 't5_zero_emission_vehicles': (142600, 177300),
    't6_reduce_idling': (5700, 3700), 'e1_decarbonize_grid': (47700, 0), 'b1_b2_natural_gas': (None, None),
    'b1_b2_electricity': (None, None), 'b1_b2_propane': (None, None), 'ind1_refrigerants': (284700, 940200),
    'sw1_divert_waste': (5800, 11700), 'sw2_methane_capture': (0, 55700), 'ww1_ww2_water_energy': (21700, 0),
    'ww3_wastewater_methane': (4200, 7400), 'ag1_agricultural_equipment': (11000, 20000),
    'sp1_retire_chp': (11200, 39200), 'sp2_industrial_electrification': (49000, 147000),
    'sp3_residential_refrigerants': (67200, 228200), 'sp4_cement_ccs': (93200, 111600),
    'sp5_construction_equipment': (64700, 117300), 'sp6_zero_emission_aviation': (0, 90700),
}

loader = InstanceLoader.from_yaml(Path(sys.argv[1]).resolve())
ctx = loader.context
net = ctx.get_node('net_emissions')


def net_by_cat():
    df = net.get_output_pl()
    df = df.filter(pl.col('Year').is_in(YEARS))
    vcol = [c for c in df.columns if c not in ('Year', 'sector', 'Forecast')][0]
    out = {}
    for row in df.iter_rows(named=True):
        out[(row['sector'], row['Year'])] = row[vcol]
    return out


def total(d, y):
    return sum(v for (c, yy), v in d.items() if yy == y)


with ctx.run():
    ctx.activate_scenario(ctx.get_scenario('baseline'))
    base = net_by_cat()
    ctx.activate_scenario(ctx.get_scenario('default'))
    impl = net_by_cat()

print(f"{'category':24} {'2022':>7} {'EPIC':>6} | {'BAU35':>6} {'EPIC':>6} | {'BAU45':>6} {'EPIC':>6} | {'IMPL35':>6} {'IMPL45':>6}")
for c in CATS:
    v = [base.get((c, y), 0) / 1e6 for y in YEARS]
    t = TARGET[c]
    i = [impl.get((c, y), 0) / 1e6 for y in (2035, 2045)]
    flag = ' <' if any(abs(round(a, 2) - b) > 0.011 for a, b in zip(v, t)) else ''
    print(f'{c:24} {v[0]:7.3f} {t[0]:6.2f} | {v[1]:6.3f} {t[1]:6.2f} | {v[2]:6.3f} {t[2]:6.2f} | {i[0]:6.3f} {i[1]:6.3f}{flag}')
print(f"{'TOTAL':24} {total(base, 2022) / 1e6:7.3f} {22.39:6.2f} | {total(base, 2035) / 1e6:6.3f} {15.61:6.2f} | "
      f"{total(base, 2045) / 1e6:6.3f} {12.10:6.2f} | {total(impl, 2035) / 1e6:6.3f} {total(impl, 2045) / 1e6:6.3f}")

na = ctx.get_node('no_action_bau_emissions').get_output_pl()
na = {r['Year']: r[[c for c in na.columns if c not in ('Year', 'Forecast')][0]] for r in na.iter_rows(named=True)}
print(f'No-Action BAU reference: 2035 {na[2035] / 1e6:.3f} (EPIC 23.04), 2045 {na[2045] / 1e6:.3f} (EPIC 23.12)')

print('\nMarginal impact of each action in the implementation scenario (t), vs Appendix E standalone estimate')
impl_tot = {y: total(impl, y) for y in (2035, 2045)}
for aid, (e35, e45) in MEASURES.items():
    act = ctx.get_node(aid)
    with ctx.run():
        ctx.activate_scenario(ctx.get_scenario('default'))
        act.enabled_param.set(False)
        d = net_by_cat()
        act.enabled_param.set(True)
    imp = [total(d, y) - impl_tot[y] for y in (2035, 2045)]
    fmt = lambda x: '   n/a' if x is None else f'{x:>9,.0f}'
    print(f'{aid:38} {imp[0]:>9,.0f} {fmt(e35)} | {imp[1]:>9,.0f} {fmt(e45)}')
