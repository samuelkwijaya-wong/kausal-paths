"""Generate configs/sandiego-region.yaml from the SANDAG Roadmap appendices B, D and E.

All numbers are transcribed from the appendix tables; derived values are computed here so
that each one can be traced back to its source table.
"""
import yaml

LB = 0.00045359237  # t per lb

# ---------------------------------------------------------------- demographics (D.1)
POP = {2022: 3287306, 2026: 3302237, 2029: 3334675, 2032: 3373033, 2035: 3404362, 2040: 3432211, 2045: 3416231}
JOBS = {2022: 2139083, 2026: 2160403, 2029: 2181532, 2032: 2201223, 2035: 2231573, 2040: 2289762, 2045: 2331407}
MFG = {2022: 126650, 2026: 120865, 2029: 121999, 2032: 125751, 2035: 134142, 2040: 149065, 2045: 160579}
HOUSING = {2022: 1235642, 2026: 1287570, 2029: 1320010, 2032: 1346977, 2035: 1372884, 2040: 1410615, 2045: 1424538}


def index(series):
    base = series[2022]
    return {y: v / base for y, v in series.items()}


# ---------------------------------------------------------------- on-road (B.3, B.8, D.4, E.1-E.6)
WEEKDAYS = 347
vmt_wd = {2022: 71244124 + 6862024, 2035: 73453955, 2045: 73313426}
vmt = {y: v * WEEKDAYS / 1e6 for y, v in vmt_wd.items()}  # Mmi/a
onroad_2022 = 7804938 + 2276300
ef_onroad_2022 = onroad_2022 / vmt[2022]  # g/mi (t / Mmi)
onroad_labau = {2035: 5812000, 2045: 2374000}  # D.4 incl. EV charging load and T-5 carve-out
ef_labau = {y: onroad_labau[y] / vmt[y] for y in (2035, 2045)}
t5 = {2035: 142600, 2045: 177300}  # E.5
ef_t5 = {y: -t5[y] / vmt[y] for y in (2035, 2045)}
ef_default = {y: ef_labau[y] + ef_t5[y] for y in (2035, 2045)}
vmt_measures = {
    't1_public_transit': (193400, 153600),
    't2_active_transportation': (124300, 64600),
    't3_flexible_fleets': (136400, 53300),
    't4_transportation_demand_management': (59200, 47500),
}
vmt_measure_mmi = {k: {2035: -a / ef_default[2035], 2045: -b / ef_default[2045]} for k, (a, b) in vmt_measures.items()}

# ---------------------------------------------------------------- electricity (B.4, B.5, D.5-D.7)
LOSS = 1.082
sales_2022 = {'sdge': 6331771, 'da': 3711568, 'cca': 6104050}  # MWh
ef_2022 = {'sdge': 508.0, 'da': 641.0}
e_before_adj = 3684429
rest = e_before_adj - sum(sales_2022[p] * LOSS * ef_2022[p] * LB for p in ('sdge', 'da'))
ef_2022['cca'] = rest / (sales_2022['cca'] * LOSS * LB)
sales_future = {  # D.6, GWh -> MWh
    'sdge': {2035: 4680e3, 2045: 4118e3},
    'cca': {2035: (9425 + 1589) * 1e3, 2045: (11836 + 1871) * 1e3},
    'da': {2035: 4400e3, 2045: 4766e3},
}
ef_future = {  # D.5, lb/MWh
    'sdge': {2030: 368, 2035: 92, 2040: 46, 2045: 0},
    'da': {2030: 417, 2035: 104, 2040: 52, 2045: 0},
    'cca': {2035: 0, 2040: 0, 2045: 0},
}
SELF_GEN = 435600  # B.5, D.7
ca_grid = {2022: 499, 2035: 78, 2045: 0}  # B.14, D.14

# ---------------------------------------------------------------- water (B.14-B.16, D.14)
upstream_mwh = {
    2022: (142374 * 1873 + 270806 * 1767) / 1000,
    2035: (129036 * 1873 + 245436 * 1767) / 1000,
    2045: (141853 * 1873 + 269814 * 1767) / 1000,
}
local_mwh_2022 = 320869821 / 1000
local_mwh_2035 = 21700 / (LOSS * ef_future['sdge'][2035] * LB)  # derived from D.7/D.14

# ---------------------------------------------------------------- natural gas (B.6, D.8)
NG_EF = 0.00545
ng_combustion = {2022: 3390400 - 470700, 2035: 2927500, 2045: 2917400}
ng_therms = {y: v / NG_EF for y, v in ng_combustion.items()}
ng_fugitive = {2022: 54700, 2035: 54900, 2045: 54600}
ng_leak_ratio = {y: ng_fugitive[y] / ng_combustion[y] for y in ng_combustion}
NG_ADJ = 35100 + 4100  # cogeneration thermal output + utility cogeneration heat

# ---------------------------------------------------------------- waste (B.12, D.12)
waste_2022 = 3473333
waste_labau = {2035: 1831122, 2045: 1818582}
cap_2022, cap_bau = 0.75, 0.85
ef_waste_2022 = 317800 / (waste_2022 * (1 - cap_2022) * 0.9)
ef_waste = {2035: 84200 / (waste_labau[2035] * (1 - cap_bau) * 0.9), 2045: 83600 / (waste_labau[2045] * (1 - cap_bau) * 0.9)}
pop_idx = index(POP)
waste_noaction = {y: waste_2022 * pop_idx[y] for y in (2035, 2045)}

# ---------------------------------------------------------------- B-1/B-2 propane (E.8)
PROPANE_T_PER_MMBTU = (62.87 + 3.0e-3 * 25 + 0.6e-3 * 298) / 1000  # EPA emission factor hub

CONSTRUCTION_IDX = {2022: 1.0, 2035: 1.05, 2045: 1.08}  # D.9 (percent only)
VMT_DRIVER_IDX = {2022: 1.0, 2035: 30900 / 29700, 2045: 31100 / 29700}  # D.10 transport, "~4 % / 5 %" in D.9


def r(v, nd=6):
    return float(f'{v:.{nd}g}')


def series(d, nd=7):
    hist = [[2022, r(d[2022], nd)]]
    fc = [[y, r(v, nd)] for y, v in sorted(d.items()) if y > 2022]
    return hist, fc


def const(v, nd=7):
    return {2022: v, 2045: v}


def node(id, name, type, quantity, unit, values=None, desc=None, inputs=None, outputs=None, **extra):
    n = {'id': id, 'name': name, 'type': type, 'quantity': quantity, 'unit': unit}
    if desc:
        n['description'] = desc
    if values is not None:
        h, f = series(values)
        n['historical_values'] = h
        if f:
            n['forecast_values'] = f
        n['input_dataset_processors'] = ['LinearInterpolation']
    if inputs:
        n['input_nodes'] = inputs
    if outputs:
        n['output_nodes'] = outputs
    n.update(extra)
    return n


def to_sector(cat):
    return [{'id': 'net_emissions', 'to_dimensions': [{'id': 'sector', 'categories': [cat]}]}]


def action(id, name, group, quantity, unit, values, output, desc, nd=7):
    vals = {2022: 0.0, **values}
    a = node(id, name, 'simple.AdditiveAction', quantity, unit, vals, desc, outputs=[output] if isinstance(output, str) else output)
    a['group'] = group
    return a


def emission_action(id, name, group, v2035, v2045, output, desc):
    return action(id, name, group, 'emissions', 't/a', {2035: -v2035, 2045: -v2045}, output, desc)


nodes = []
actions = []
SRC_B, SRC_D, SRC_E = 'Roadmap Appendix B', 'Roadmap Appendix D', 'Roadmap Appendix E'

# ---------------- drivers
nodes += [
    node('population', 'Population', 'simple.AdditiveNode', 'population', 'person', POP,
         f'SANDAG Series 15 regional growth forecast ({SRC_D}, Table D.1). 2045 is a straight-line interpolation by EPIC.'),
    node('population_index', 'Population relative to 2022', 'simple.AdditiveNode', 'ratio', 'dimensionless', index(POP),
         f'Population divided by the 2022 population ({SRC_D}, Table D.1).'),
    node('jobs_index', 'Jobs relative to 2022', 'simple.AdditiveNode', 'ratio', 'dimensionless', index(JOBS),
         f'Total jobs divided by 2022 jobs ({SRC_D}, Table D.1).'),
    node('manufacturing_jobs_index', 'Manufacturing jobs relative to 2022', 'simple.AdditiveNode', 'ratio', 'dimensionless', index(MFG),
         f'Manufacturing jobs divided by 2022 manufacturing jobs ({SRC_D}, Table D.1).'),
    node('housing_index', 'Housing units relative to 2022', 'simple.AdditiveNode', 'ratio', 'dimensionless', index(HOUSING),
         f'Housing units divided by 2022 housing units ({SRC_D}, Table D.1).'),
    node('construction_jobs_index', 'Construction jobs relative to 2022', 'simple.AdditiveNode', 'ratio', 'dimensionless', CONSTRUCTION_IDX,
         f'Construction jobs change from 2022, given only as percentages in {SRC_D}, Table D.9.'),
    node('vmt_driver_index', 'VMT growth driver used for scaled categories', 'simple.AdditiveNode', 'ratio', 'dimensionless', VMT_DRIVER_IDX,
         f'VMT growth EPIC used to scale industrial and other-fuel transport emissions ({SRC_D}, Tables D.9 and D.10). '
         'Note: this rises about 4-5 %, while the on-road VMT in Table D.4 falls about 6 %.'),
]


def scaled(id, name, base, driver, cat_desc):
    """2022 emissions held in a base node, grown with a driver index."""
    nodes.append(node(f'{id}_2022_level', f'{name} (2022 level)', 'simple.AdditiveNode', 'emissions', 't/a', const(base),
                      f'2022 value. {cat_desc}'))
    n = node(id, name, 'formula.FormulaNode', 'emissions', 't/a', desc=cat_desc, inputs=[f'{id}_2022_level', driver],
             params={'formula': f'{id}_2022_level * {driver}'})
    return n


# ---------------- on-road
nodes += [
    node('onroad_vmt', 'On-road vehicle miles travelled', 'simple.AdditiveNode', 'mileage', 'Mmi/a', vmt,
         f'SANDAG ABM15.2.1 weekday VMT ({SRC_B}, Tables B.3 and B.8; {SRC_D}, Table D.4) × 347 weekdays per year.'),
    node('onroad_emission_factor', 'On-road average emission factor', 'simple.AdditiveNode', 'emission_factor', 'g/mi', const(ef_onroad_2022),
         f'2022 average emission factor for all vehicles, derived from {SRC_B} Tables B.3 and B.8 '
         '(emissions ÷ annual VMT). Held at the 2022 level; state and federal vehicle rules are an action.'),
    node('onroad_tailpipe_emissions', 'On-road emissions from VMT', 'simple.MultiplicativeNode', 'emissions', 't/a',
         inputs=['onroad_vmt', 'onroad_emission_factor']),
    node('onroad_emissions', 'On-road transportation emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         desc='Passenger cars, light-duty and heavy-duty vehicles.', inputs=['onroad_tailpipe_emissions'],
         outputs=to_sector('onroad_transportation')),
]
actions.append(action(
    'emfac2025_vehicle_regulations', 'State and federal vehicle regulations (EMFAC2025)', 'state_federal', 'emission_factor', 'g/mi',
    {2035: ef_labau[2035] - ef_onroad_2022, 2045: ef_labau[2045] - ef_onroad_2022}, 'onroad_emission_factor',
    f'Advanced Clean Cars II, federal multi-pollutant standards, heavy-duty Phase 3 and Clean Trucks, as modelled in EMFAC2025 '
    f'({SRC_D}, section 5.1 and Table D.4). Includes the emissions of the added EV charging load (121,000 t in 2035) '
    'and excludes the regional EV programmes credited to measure T-5.'))

# ---------------- electricity
nodes.append(node('grid_loss_factor', 'Transmission and distribution loss factor', 'simple.AdditiveNode', 'ratio', 'dimensionless',
                  const(LOSS), f'{SRC_B}, Table B.5.'))
prov_names = {'sdge': 'SDG&E bundled', 'cca': 'Community choice aggregators (CCAs)', 'da': 'Direct Access providers'}
for p, pname in prov_names.items():
    sv = {2022: sales_2022[p], **sales_future[p]}
    nodes += [
        node(f'electricity_sales_{p}', f'Electricity sales: {pname}', 'simple.AdditiveNode', 'energy', 'MWh/a', sv,
             f'{SRC_B}, Table B.5 (2022); {SRC_D}, Table D.6 (2035, 2045). CCAs are San Diego Community Power and Clean Energy Alliance.'),
        node(f'electricity_emission_factor_{p}', f'Electricity emission factor: {pname}', 'simple.AdditiveNode', 'emission_factor', 'lb/MWh',
             const(ef_2022[p]),
             f'2022 power content label factor ({SRC_B}, Table B.4), held constant; state law is an action.'
             + (' The CCA factor is the sales-weighted value implied by the Table B.5 total.' if p == 'cca' else '')),
        node(f'electricity_emissions_{p}', f'Electricity emissions: {pname}', 'simple.MultiplicativeNode', 'emissions', 't/a',
             inputs=[f'electricity_sales_{p}', 'grid_loss_factor', f'electricity_emission_factor_{p}']),
    ]
    delta = {y: v - ef_2022[p] for y, v in ef_future[p].items()}
    actions.append(action(
        f'rps_{p}', f'SB 100 / SB 1020 clean electricity: {pname}', 'state_federal', 'emission_factor', 'lb/MWh', delta,
        f'electricity_emission_factor_{p}',
        f'Renewable and zero-carbon targets (SB 100, SB 1020)' + (' and the CCAs\' 100 %-by-2035 commitments' if p == 'cca' else '')
        + f'. Emission factors from {SRC_D}, Table D.5.'))
nodes += [
    node('electricity_sales_emissions', 'Emissions from electricity sales', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=[f'electricity_emissions_{p}' for p in prov_names]),
    node('electricity_sales_total', 'Total electricity sales', 'simple.AdditiveNode', 'energy', 'MWh/a',
         inputs=[f'electricity_sales_{p}' for p in prov_names]),
    node('electricity_average_emission_factor', 'Region-wide average electricity emission factor', 'formula.FormulaNode',
         'emission_factor', 't/MWh', inputs=['electricity_sales_emissions', 'electricity_sales_total'],
         params={'formula': 'electricity_sales_emissions / electricity_sales_total'},
         desc='Used to value added electricity demand from building electrification.'),
    node('additional_electricity_demand', 'Additional electricity demand from measures', 'simple.AdditiveNode', 'energy', 'MWh/a',
         const(0.0), 'Electricity added by Roadmap measures (building electrification).'),
    node('additional_electricity_demand_emissions', 'Emissions from additional electricity demand', 'simple.MultiplicativeNode',
         'emissions', 't/a', inputs=['additional_electricity_demand', 'electricity_average_emission_factor']),
    node('electricity_self_generation_emissions', 'Natural gas used for on-site self-generation', 'simple.AdditiveNode',
         'emissions', 't/a', const(SELF_GEN),
         f'Moved from the natural gas category to electricity; held at the 2022 level ({SRC_B}, Table B.5; {SRC_D}, Table D.7).'),
]
elec = node('electricity_emissions', 'Electricity emissions', 'generic.GenericNode', 'emissions', 't/a',
            desc=f'Electricity sales emissions plus self-generation, minus electricity counted in the water and rail '
                 f'categories ({SRC_B}, Table B.5).',
            inputs=['electricity_sales_emissions', 'electricity_self_generation_emissions', 'additional_electricity_demand_emissions',
                    {'id': 'water_treatment_grid_emissions', 'tags': ['arithmetic_inverse']},
                    {'id': 'rail_electric_emissions', 'tags': ['arithmetic_inverse']}],
            outputs=to_sector('electricity'))
elec['params'] = {'operations': 'add'}
nodes.append(elec)

# ---------------- natural gas
nodes += [
    node('natural_gas_use', 'Natural gas use', 'simple.AdditiveNode', 'energy', 'thm/a', ng_therms,
         f'Metered sales net of gas used for on-site self-generation, derived from the emissions in {SRC_B} Table B.6 '
         f'and {SRC_D} Table D.8 at 0.00545 t/therm. The therm figures printed in Table D.8 do not reproduce its own total.'),
    node('natural_gas_emission_factor', 'Natural gas emission factor', 'simple.AdditiveNode', 'emission_factor', 't/thm',
         const(NG_EF), f'CARB statewide inventory ({SRC_B}, Table B.6).'),
    node('natural_gas_combustion_emissions', 'Natural gas combustion emissions', 'simple.MultiplicativeNode', 'emissions', 't/a',
         inputs=['natural_gas_use', 'natural_gas_emission_factor']),
    node('natural_gas_leak_ratio', 'Pipeline leaks relative to combustion emissions', 'simple.AdditiveNode', 'ratio', 'dimensionless',
         ng_leak_ratio, f'Fugitive pipeline emissions (EPA FLIGHT) divided by combustion emissions ({SRC_B} Table B.6, {SRC_D} Table D.8).'),
    node('natural_gas_fugitive_emissions', 'Natural gas pipeline leaks', 'formula.FormulaNode', 'emissions', 't/a',
         inputs=['natural_gas_combustion_emissions', 'natural_gas_leak_ratio'],
         params={'formula': 'natural_gas_combustion_emissions * natural_gas_leak_ratio'}),
    node('natural_gas_cogeneration_adjustment', 'Cogeneration heat output', 'simple.AdditiveNode', 'emissions', 't/a',
         const(NG_ADJ), f'Useful thermal output of self-serve and utility cogeneration plants ({SRC_B}, Table B.6).'),
    node('natural_gas_emissions', 'Natural gas emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['natural_gas_combustion_emissions', 'natural_gas_fugitive_emissions', 'natural_gas_cogeneration_adjustment'],
         outputs=to_sector('natural_gas')),
]

# ---------------- industrial (B.7, D.9)
ind_desc = f'State inventory scaled to the region ({SRC_B}, Table B.7) and projected with the matching SANDAG driver ({SRC_D}, section 5.4).'
nodes += [
    scaled('industrial_manufacturing', 'Industrial: cement, lubricants, solvents, semiconductors, CO2/soda ash', 530000, 'manufacturing_jobs_index', ind_desc),
    scaled('industrial_residential_hfc', 'Industrial: residential refrigerants and foams', 410000, 'housing_index', ind_desc),
    scaled('industrial_commercial_hfc', 'Industrial: commercial and industrial refrigerants and foams', 1020000, 'jobs_index', ind_desc),
    scaled('industrial_transport_hfc', 'Industrial: vehicle refrigerants and lubricants', 410000, 'vmt_driver_index', ind_desc),
    scaled('industrial_limestone', 'Industrial: limestone and dolomite', 10000, 'construction_jobs_index', ind_desc),
    node('industrial_sf6', 'Industrial: SF6 from electricity transmission', 'simple.AdditiveNode', 'emissions', 't/a', const(17000),
         ind_desc + ' Held constant.'),
    node('industrial_emissions', 'Industrial emissions (high-GWP gases and processes)', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['industrial_manufacturing', 'industrial_residential_hfc', 'industrial_commercial_hfc', 'industrial_transport_hfc',
                 'industrial_limestone', 'industrial_sf6'], outputs=to_sector('industrial')),
]

# ---------------- other fuels (B.9, D.10)
of_desc = f'State inventory scaled to the region ({SRC_B}, Table B.9), projected with the matching driver ({SRC_D}, section 5.5).'
nodes += [
    node('other_fuels_agriculture', 'Other fuels: agriculture', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 40900, 2035: 8600, 2045: 0}, of_desc + ' Trend of the regional share of state agricultural revenue.'),
    scaled('other_fuels_commercial', 'Other fuels: commercial', 205100, 'manufacturing_jobs_index', of_desc),
    scaled('other_fuels_industrial', 'Other fuels: industrial', 459700, 'manufacturing_jobs_index', of_desc),
    scaled('other_fuels_residential', 'Other fuels: residential (propane, wood, etc.)', 123800, 'population_index', of_desc),
    scaled('other_fuels_transportation', 'Other fuels: transportation', 29700, 'vmt_driver_index', of_desc),
    node('other_fuels_emissions', 'Other fuels emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['other_fuels_agriculture', 'other_fuels_commercial', 'other_fuels_industrial', 'other_fuels_residential',
                 'other_fuels_transportation'], outputs=to_sector('other_fuels')),
]

# ---------------- off-road (B.10, D.11)
nodes += [
    node('offroad_construction_mining', 'Off-road: construction and mining equipment', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 154900, 2035: 155300, 2045: 156400}, f'CARB OFFROAD2021 ({SRC_B}, Table B.10; {SRC_D}, Table D.11).'),
    node('offroad_other', 'Off-road: other equipment', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 676100 - 154900, 2035: 677300 - 155300, 2045: 676200 - 156400},
         f'Airport ground support, cargo handling, industrial, forklifts, lawn and garden, light commercial, military, '
         f'pleasure craft, portable, recreational and refrigeration units. CARB OFFROAD2021 ({SRC_B}, Table B.10; {SRC_D}, Table D.11).'),
    node('offroad_emissions', 'Off-road transportation emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['offroad_construction_mining', 'offroad_other'], outputs=to_sector('offroad')),
]

# ---------------- solid waste (B.11, B.12, D.12)
nodes += [
    node('waste_disposed', 'Solid waste disposed in landfills', 'simple.AdditiveNode', 'mass', 'short_ton/a',
         {2022: waste_2022, **waste_noaction},
         f'2022 disposal ({SRC_B}, Table B.12) grown with population ({SRC_D}, section 5.7). SB 1383 is an action.'),
    node('waste_emission_factor', 'Mixed waste emission factor', 'simple.AdditiveNode', 'emission_factor', 't/short_ton',
         const(ef_waste_2022), f'Weighted WARM v16 landfill factor for the statewide waste composition ({SRC_B}, Tables B.11-B.12).'),
    node('landfill_gas_capture_rate', 'Landfill gas capture rate', 'simple.AdditiveNode', 'ratio', 'dimensionless', const(cap_2022),
         f'{SRC_B}, Table B.12.'),
    node('landfill_oxidation_rate', 'Landfill oxidation rate', 'simple.AdditiveNode', 'ratio', 'dimensionless', const(0.1),
         f'ICLEI U.S. Community Protocol default ({SRC_B}, Table B.12).'),
    node('solid_waste_landfill_emissions', 'Landfill methane from waste disposed', 'formula.FormulaNode', 'emissions', 't/a',
         inputs=['waste_disposed', 'waste_emission_factor', 'landfill_gas_capture_rate', 'landfill_oxidation_rate'],
         params={'formula': 'waste_disposed * waste_emission_factor * (1 - landfill_gas_capture_rate) * (1 - landfill_oxidation_rate)'}),
    node('solid_waste_emissions', 'Solid waste emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['solid_waste_landfill_emissions'], outputs=to_sector('solid_waste')),
]
actions += [
    action('sb1383_organics_diversion', 'SB 1383: organic waste diverted from landfills', 'state_federal', 'mass', 'short_ton/a',
           {y: waste_labau[y] - waste_noaction[y] for y in (2035, 2045)}, 'waste_disposed',
           f'75 % of 2016 organics diverted; about 44 % less waste landfilled ({SRC_D}, section 5.7 and Table D.12).'),
    action('sb1383_waste_composition', 'SB 1383: lower organic content of landfilled waste', 'state_federal', 'emission_factor', 't/short_ton',
           {y: ef_waste[y] - ef_waste_2022 for y in (2035, 2045)}, 'waste_emission_factor',
           f'Mixed waste factor after SB 1383 ({SRC_D}, Table D.12).'),
    action('landfill_methane_regulation', 'CARB / APCD landfill methane regulation (85 % capture)', 'state_federal', 'ratio', 'dimensionless',
           {2035: cap_bau - cap_2022, 2045: cap_bau - cap_2022}, 'landfill_gas_capture_rate',
           f'San Diego County APCD default capture rate ({SRC_D}, section 5.7).'),
]

# ---------------- aviation (B.13, D.13)
nodes.append(node('aviation_emissions', 'Civil aviation emissions', 'simple.AdditiveNode', 'emissions', 't/a',
                  {2022: 309500, 2035: 434400, 2045: 453500},
                  f'Landing and take-off cycle at San Diego International, McClellan-Palomar and county airports '
                  f'({SRC_B}, Table B.13; {SRC_D}, Table D.13).', outputs=to_sector('aviation')))

# ---------------- water (B.14-B.16, D.14)
nodes += [
    node('water_upstream_electricity', 'Electricity for imported water supply', 'simple.AdditiveNode', 'energy', 'MWh/a', upstream_mwh,
         f'Imported treated and raw water × upstream energy intensity (1,873 and 1,767 kWh/acre-foot) '
         f'({SRC_B}, Table B.14; volumes for 2035 and 2045 from {SRC_D}, Table D.14).'),
    node('california_grid_emission_factor', 'California average electricity emission factor', 'simple.AdditiveNode',
         'emission_factor', 'lb/MWh', const(ca_grid[2022]), f'eGRID 2022 CAMX ({SRC_B}, Table B.14); state law is an action.'),
    node('water_upstream_emissions', 'Water: upstream supply and conveyance', 'simple.MultiplicativeNode', 'emissions', 't/a',
         inputs=['water_upstream_electricity', 'california_grid_emission_factor']),
    node('water_local_electricity', 'Electricity for local water treatment', 'simple.AdditiveNode', 'energy', 'MWh/a',
         {2022: local_mwh_2022, 2035: local_mwh_2035, 2045: local_mwh_2035},
         f'2022 from {SRC_B} Table B.15. 2035 is derived from the local treatment emissions in {SRC_D} Table D.14 '
         '(21,700 t at the SDG&E factor); held flat to 2045.'),
    node('water_local_emission_factor', 'Emission factor of water treatment electricity', 'simple.AdditiveNode', 'emission_factor',
         'lb/MWh', inputs=['electricity_emission_factor_sdge'],
         desc='Water treatment plants are assumed to use SDG&E bundled electricity (Appendix B default).'),
    node('water_local_emissions', 'Water: local treatment', 'simple.MultiplicativeNode', 'emissions', 't/a',
         inputs=['water_local_electricity', 'grid_loss_factor', 'water_local_emission_factor']),
    node('water_treatment_grid_emissions', 'Water treatment electricity counted in the water category', 'simple.MultiplicativeNode',
         'emissions', 't/a', inputs=['water_local_electricity', 'grid_loss_factor', 'electricity_emission_factor_sdge'],
         desc='Subtracted from the electricity category to avoid double counting.'),
    node('water_emissions', 'Water supply and treatment emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['water_upstream_emissions', 'water_local_emissions'], outputs=to_sector('water')),
]
actions.append(action('rps_california_grid', 'SB 100 / SB 1020 clean electricity: California grid', 'state_federal', 'emission_factor',
                      'lb/MWh', {2035: ca_grid[2035] - ca_grid[2022], 2045: ca_grid[2045] - ca_grid[2022]},
                      'california_grid_emission_factor', f'{SRC_D}, Table D.14.'))

# ---------------- marine (B.17, D.15)
nodes.append(node('marine_emissions', 'Marine vessel emissions', 'simple.AdditiveNode', 'emissions', 't/a',
                  {2022: 201000, 2035: 242400, 2045: 273900},
                  f'Ocean-going vessels and commercial harbor craft, CARB OFFROAD2021 ({SRC_B}, Table B.17; {SRC_D}, Table D.15).',
                  outputs=to_sector('marine')))

# ---------------- agriculture (B.18-B.23, D.16)
AG_I = 10 / 15  # 2045 interpolated between the 2035 and 2050 columns of D.16
nodes += [
    node('agriculture_equipment', 'Agriculture: equipment', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 73300, 2035: 68200, 2045: 68200 + (64700 - 68200) * AG_I},
         f'CARB OFFROAD2021 ({SRC_B}, Table B.19; {SRC_D}, Table D.16, 2045 interpolated from the 2050 column).'),
    node('agriculture_livestock', 'Agriculture: enteric fermentation and manure', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 36000 + 41100, 2035: 37200 + 42500, 2045: 79700 + (83600 - 79700) * AG_I},
         f'{SRC_B}, Tables B.20-B.21; {SRC_D}, Table D.16 (2045 interpolated).'),
    node('agriculture_soil', 'Agriculture: soil management', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 33800, 2035: 54400, 2045: 54400 + (56400 - 54400) * AG_I},
         f'{SRC_B}, Tables B.22-B.23; {SRC_D}, Table D.16 (2045 interpolated).'),
    node('agriculture_emissions', 'Agriculture emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['agriculture_equipment', 'agriculture_livestock', 'agriculture_soil'], outputs=to_sector('agriculture')),
]

# ---------------- wastewater (B.24, D.17)
nodes.append(scaled('wastewater_treatment', 'Wastewater treatment plants', 49000, 'population_index',
                    f'Reported emissions of the three largest plants, scaled to all regional influent ({SRC_B}, Table B.24), '
                    f'grown with population ({SRC_D}, Table D.17).'))
nodes.append(node('wastewater_emissions', 'Wastewater emissions', 'simple.AdditiveNode', 'emissions', 't/a',
                  inputs=['wastewater_treatment'], outputs=to_sector('wastewater')))

# ---------------- rail (B.25, D.18)
nodes += [
    node('rail_diesel_emissions', 'Rail: diesel', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 2200 + 1280613 * 10.21 / 1000, 2035: 800 + 4900, 2045: 600 + 65},
         f'Freight (OFFROAD2021) and light rail diesel ({SRC_B}, Table B.25; {SRC_D}, Table D.18). '
         'Includes CARB\'s 2023 locomotive rule, which was repealed in June 2025.'),
    node('rail_electric_emissions', 'Rail: electric', 'simple.AdditiveNode', 'emissions', 't/a',
         {2022: 26200 - 1280613 * 10.21 / 1000, 2035: 300 + 2700, 2045: 0},
         f'Electric light rail and freight ({SRC_B}, Tables B.5 and B.25; {SRC_D}, Table D.18). '
         'Subtracted from the electricity category.'),
    node('rail_emissions', 'Rail emissions', 'simple.AdditiveNode', 'emissions', 't/a',
         inputs=['rail_diesel_emissions', 'rail_electric_emissions'], outputs=to_sector('rail')),
]

# ---------------- No-Action BAU reference line (D.3)
nodes += [
    node('no_action_emissions_per_capita', 'No-Action BAU: emissions per person', 'simple.AdditiveNode', 'emission_factor', 't/person/a',
         const(22250000 / POP[2022]),
         f'2022 emissions per person held constant ({SRC_D}, Table D.3). Uses the 22.25 MMT total of Table D.2, '
         'not the 22.39 MMT of Appendix B.'),
    node('no_action_bau_emissions', 'No-Action BAU emissions (reference)', 'simple.MultiplicativeNode', 'emissions', 't/a',
         inputs=['no_action_emissions_per_capita', 'population'],
         desc=f'Reference line: 2022 per-capita emissions × population ({SRC_D}, section 4). Not part of the net emissions total.'),
]

# ================================================================ Roadmap measures (E)
actions += [
    action('regional_plan_2025', 'Draft 2025 Regional Plan (Build vs. No Build)', 'regional_plan', 'mileage', 'Mmi/a',
           {2035: 0.0, 2045: 0.0}, 'onroad_vmt',
           f'Placeholder: the VMT difference between the Regional Plan "Build" and "No Build" scenarios is not given in '
           f'{SRC_E} (only in Figure E.1). Values needed from SANDAG\'s Draft 2025 Regional Plan.'),
]
vm_names = {
    't1_public_transit': ('T-1 Reduce VMT through increased public transit use',
                          '+2.5 / +5.0 percentage points transit mode share above the Regional Plan (Table E.1).'),
    't2_active_transportation': ('T-2 Reduce VMT through active transportation',
                                 '+4.2 / +5.0 percentage points biking mode share (Table E.2).'),
    't3_flexible_fleets': ('T-3 Reduce VMT through flexible fleets', '+4.5 percentage points micromobility mode share (Table E.3).'),
    't4_transportation_demand_management': ('T-4 Reduce VMT through transportation demand management',
                                            'One / two more telework days per week in telecommutable industries (Table E.4).'),
}
for k, (nm, d) in vm_names.items():
    a, b = vmt_measures[k]
    actions.append(action(k, nm, 'transportation', 'mileage', 'Mmi/a', vmt_measure_mmi[k], 'onroad_vmt',
                          f'{d} VMT avoided is back-calculated from EPIC\'s reductions ({a:,} t in 2035, {b:,} t in 2045, '
                          f'{SRC_E}) at the implementation-scenario vehicle emission factor.'))
actions += [
    action('t5_zero_emission_vehicles', 'T-5 Increase the adoption of zero-emission vehicles', 'transportation', 'emission_factor', 'g/mi',
           ef_t5, 'onroad_emission_factor',
           f'Regional EV programmes (SDG&E Power Your Drive for Fleets, APCD Clean Air for All): 142,600 t in 2035 and 177,300 t '
           f'in 2045 ({SRC_E}, Table E.5), carved out of the EMFAC2025 adoption rate.'),
    emission_action('t6_reduce_idling', 'T-6 Reduce fuel use from idling', 'transportation', 5700, 3700, 'onroad_emissions',
                    f'76 roundabouts and 236 retimed signals by 2045 ({SRC_E}, Table E.6).'),
    emission_action('e1_decarbonize_grid', 'E-1 Decarbonize the regional electric grid', 'energy', 47700, 0, 'electricity_emissions',
                    f'Distributed energy resources supply 20 % of demand by 2045 ({SRC_E}, Table E.7). No 2045 reduction because '
                    'the grid is already zero-carbon.'),
    action('b1_b2_natural_gas', 'B-1/B-2 Building efficiency and electrification: natural gas saved', 'buildings', 'energy', 'thm/a',
           {2035: -218e6, 2045: -385e6}, 'natural_gas_use', f'NREL ResStock/ComStock measures ({SRC_E}, Table E.8).'),
    action('b1_b2_electricity', 'B-1/B-2 Building efficiency and electrification: electricity added', 'buildings', 'energy', 'MWh/a',
           {2035: 918e3, 2045: 1624e3}, 'additional_electricity_demand', f'{SRC_E}, Table E.8.'),
    emission_action('b1_b2_propane', 'B-1/B-2 Building efficiency and electrification: propane saved', 'buildings',
                    378000 * PROPANE_T_PER_MMBTU, 670000 * PROPANE_T_PER_MMBTU, 'other_fuels_emissions',
                    f'378,000 / 670,000 MMBtu of propane ({SRC_E}, Table E.8) × EPA factor 63.1 kg CO2e/MMBtu.'),
    emission_action('ind1_refrigerants', 'IND-1 Reduce short-lived climate pollutant emissions', 'industry', 284700, 940200,
                    'industrial_emissions', f'42 % / 75 % of commercial, industrial and transport refrigerants replaced with '
                    f'low-GWP alternatives ({SRC_E}, Table E.9).'),
    emission_action('ind2_industrial_energy', 'IND-2 Reduce energy intensity of industrial facilities', 'industry', 0, 0,
                    'industrial_emissions', f'Not quantified separately; partly covered by B-1, B-2 and E-1 ({SRC_E}, section 5.4).'),
    action('sw1_divert_waste', 'SW-1 Divert waste from landfills', 'waste', 'mass', 'short_ton/a', {2035: -127000, 2045: -254000},
           'waste_disposed', f'88 % / 100 % of organics diverted ({SRC_E}, Table E.10).'),
    action('sw2_methane_capture', 'SW-2 Increase landfill methane capture', 'waste', 'ratio', 'dimensionless', {2035: 0.0, 2045: 0.10},
           'landfill_gas_capture_rate', f'95 % capture by 2045 ({SRC_E}, Table E.11).'),
    action('ww1_ww2_water_energy', 'WW-1/WW-2 Reduce water demand and optimize water-system energy', 'water', 'emission_factor',
           'lb/MWh', {2035: -ef_future['sdge'][2035], 2045: 0.0}, 'water_local_emission_factor',
           f'Local treatment, desalination and potable reuse follow the CCA clean-electricity timeline ({SRC_E}, Table E.12).'),
    emission_action('ww3_wastewater_methane', 'WW-3 Reduce methane emissions from wastewater systems', 'water', 4200, 7400,
                    'wastewater_emissions', f'{SRC_E}, Table E.13.'),
    emission_action('ag1_agricultural_equipment', 'AG-1 Reduce emissions from agriculture operations', 'agriculture', 11000, 20000,
                    'agriculture_equipment', f'42 % / 75 % of agricultural off-road equipment electric ({SRC_E}, Table E.14).'),
]
for aid, nm in [('ag2_urban_agriculture', 'AG-2 Expand urban agriculture'),
                ('ag3_carbon_farming', 'AG-3 Increase agricultural practices that sequester carbon'),
                ('ag4_conserve_agricultural_land', 'AG-4 Conserve agricultural land')]:
    actions.append(emission_action(aid, nm, 'agriculture', 0, 0, 'agriculture_emissions',
                                   f'Not quantified: sequestration is outside the inventory boundary ({SRC_E}, section 5.7).'))
for aid, nm in [('nwl1_coastal_wetlands', 'NWL-1 Conserve coastal and wetland ecosystems'),
                ('nwl2_forest_shrubland', 'NWL-2 Conserve forest, shrubland and chaparral ecosystems'),
                ('nwl3_urban_greening', 'NWL-3 Increase urban greening')]:
    actions.append(emission_action(aid, nm, 'natural_lands', 0, 0, 'agriculture_emissions',
                                   f'Not quantified: sequestration is outside the inventory boundary ({SRC_E}, section 5.8).'))
actions += [
    emission_action('sp1_retire_chp', 'Scoping Plan 1: Retire combined heat and power facilities by 2040', 'scoping_plan', 11200, 39200,
                    'natural_gas_emissions', f'{SRC_E}, Table E.15.'),
    emission_action('sp2_industrial_electrification', 'Scoping Plan 2: Electrify 50 % of industrial natural gas by 2045', 'scoping_plan',
                    49000, 147000, 'natural_gas_emissions', f'{SRC_E}, Table E.16.'),
    emission_action('sp3_residential_refrigerants', 'Scoping Plan 3: Low-GWP refrigerants in homes', 'scoping_plan', 67200, 228200,
                    'industrial_emissions', f'{SRC_E}, Table E.17.'),
    emission_action('sp4_cement_ccs', 'Scoping Plan 4: Carbon capture for stone, clay, glass and cement', 'scoping_plan', 93200, 111600,
                    'other_fuels_emissions', f'{SRC_E}, Table E.18.'),
    emission_action('sp5_construction_equipment', 'Scoping Plan 5: Electrify construction equipment', 'scoping_plan', 64700, 117300,
                    'offroad_construction_mining', f'{SRC_E}, Table E.19.'),
    emission_action('sp6_zero_emission_aviation', 'Scoping Plan 6: 20 % zero-emission aviation fuel by 2045', 'scoping_plan', 0, 90700,
                    'aviation_emissions', f'{SRC_E}, Table E.20.'),
]

state_actions = [a['id'] for a in actions if a['group'] == 'state_federal']

sectors = [
    ('onroad_transportation', 'On-road transportation', '#E15759'),
    ('electricity', 'Electricity', '#4E79A7'),
    ('natural_gas', 'Natural gas', '#F28E2B'),
    ('industrial', 'Industrial', '#76B7B2'),
    ('other_fuels', 'Other fuels', '#59A14F'),
    ('offroad', 'Off-road transportation', '#EDC948'),
    ('solid_waste', 'Solid waste', '#B07AA1'),
    ('aviation', 'Civil aviation', '#FF9DA7'),
    ('water', 'Water', '#9C755F'),
    ('marine', 'Marine vessels', '#BAB0AC'),
    ('agriculture', 'Agriculture', '#8CD17D'),
    ('wastewater', 'Wastewater', '#86BCB6'),
    ('rail', 'Rail', '#D37295'),
]

config = {
    'id': 'sandiego-region',
    'default_language': 'en',
    'supported_languages': [],
    'name': 'San Diego Region Climate Action Roadmap (draft model)',
    'owner': 'San Diego region',
    'theme_identifier': 'default',
    'target_year': 2045,
    'model_end_year': 2045,
    'reference_year': 2022,
    'minimum_historical_year': 2022,
    'maximum_historical_year': 2022,
    'emission_unit': 't/a',
    'emission_forecast_from': 2023,
    'emission_dimensions': ['sector'],
    'features': {'baseline_visible_in_graphs': True},
    'action_groups': [
        {'id': 'state_federal', 'name': 'Adopted state and federal legislation', 'color': '#BAB0AC'},
        {'id': 'regional_plan', 'name': 'Draft 2025 Regional Plan', 'color': '#9C755F'},
        {'id': 'transportation', 'name': 'Roadmap: transportation', 'color': '#E15759'},
        {'id': 'energy', 'name': 'Roadmap: electricity', 'color': '#4E79A7'},
        {'id': 'buildings', 'name': 'Roadmap: buildings', 'color': '#F28E2B'},
        {'id': 'industry', 'name': 'Roadmap: industry', 'color': '#76B7B2'},
        {'id': 'waste', 'name': 'Roadmap: solid waste and materials', 'color': '#B07AA1'},
        {'id': 'water', 'name': 'Roadmap: water and wastewater', 'color': '#86BCB6'},
        {'id': 'agriculture', 'name': 'Roadmap: agriculture', 'color': '#8CD17D'},
        {'id': 'natural_lands', 'name': 'Roadmap: natural and working lands', 'color': '#59A14F'},
        {'id': 'scoping_plan', 'name': 'California Scoping Plan goals', 'color': '#D37295'},
    ],
    'dimensions': [{'id': 'sector', 'label': 'Emission category',
                    'categories': [{'id': i, 'label': l, 'color': c} for i, l, c in sectors]}],
    'emission_sectors': [{'id': 'net_emissions', 'name': 'Net emissions', 'is_outcome': True,
                          'input_dimensions': ['sector'], 'output_dimensions': ['sector']}],
    'nodes': nodes,
    'actions': actions,
    'pages': [{'id': 'home', 'name': 'San Diego region greenhouse gas emissions', 'path': '/', 'type': 'emission',
               'outcome_node': 'net_emissions', 'lead_title': 'San Diego Regional Climate Action Roadmap',
               'lead_paragraph': 'Draft model of the 2022 regional inventory, the legislatively-adjusted business-as-usual '
                                 'projection and the Roadmap implementation scenario, reproduced from Roadmap Appendices B, D and E.'}],
    'scenarios': [
        {'id': 'baseline', 'name': 'Legislatively-adjusted business as usual', 'all_actions_enabled': False,
         'param_values': {f'{a}.enabled': True for a in state_actions}},
        {'id': 'default', 'default': True, 'name': 'Roadmap implementation scenario', 'all_actions_enabled': True},
    ],
}

HEADER = """\
# San Diego Regional Climate Action Roadmap -- draft model.
#
# Reproduces the regional GHG inventory (2022), the legislatively-adjusted business-as-usual
# projection and the implementation scenario of the SANDAG Regional Climate Action Roadmap
# (December 2025), following the methods in its Appendices B, D and E (prepared by USD EPIC).
#
# First draft: the numbers are inline historical_values / forecast_values. They belong in
# datasets before this model is used by anyone else (see CLAUDE.md, "Actions").
# Generated by notebooks/sandiego_region/generate_config.py -- edit that script, not this file.
# See docs/sandiego-region-model.md for sources and method choices.
"""

if __name__ == '__main__':
    import sys
    out = sys.argv[1]
    with open(out, 'w') as f:
        f.write(HEADER)
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True, width=120)
    print('ef_onroad_2022', ef_onroad_2022, 'ef_labau', ef_labau, 'ef_default', ef_default)
    print('ef_cca_2022', ef_2022['cca'], 'ef_waste', ef_waste_2022, ef_waste, 'local_mwh_2035', local_mwh_2035)
