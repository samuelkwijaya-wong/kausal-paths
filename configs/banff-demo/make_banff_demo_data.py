"""
Build the dataset CSVs for the Banff illustrative demo instance (`banff-demo`).

Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap.
Not prepared or endorsed by the Town of Banff.

Every number below is typed in from the Roadmap (Town of Banff, Renewable Energy
Transition Roadmap, December 2019) and tagged with its printed page and whether it is
exact, read from a chart or interpolated. The few numbers this script *calculates*
(action ramps, the allocation of multi-sector actions to sectors, the 2026 placeholder
column) are calculated here, from those inputs, by rules written out in DATA_NOTES.md.

Run from the repository root:

    python configs/banff-demo/make_banff_demo_data.py

It writes, next to itself:

    banff_demo_data.csv           the datasets, wide format, for tools/upload_new_dataset
    banff_demo_template_2026.csv  the blank 2026 reconciliation template (upload with
                                  --keep-empty-cells)
    banff_demo_sources.csv        the sources registry

and exits non-zero if any published total fails to reconcile.
"""

# ruff: noqa: INP001, C901, PLR0912, PLR0915, PERF401  # a standalone producer script, run directly

import csv
import sys
from itertools import pairwise
from pathlib import Path

HERE = Path(__file__).parent

DEMO_NOTICE = (
    'Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap. '
    'Not prepared or endorsed by the Town of Banff.'
)
ROADMAP = 'Banff Roadmap 2019'
ASSUMPTION = 'Kausal demo assumption'
PLACEHOLDER = 'Kausal demo placeholder'

YEARS = list(range(2016, 2051))

# ---------------------------------------------------------------------------
# Appendix 2, p. 103: emissions by sector, t CO2e. Exact.
# ---------------------------------------------------------------------------
SECTORS = [
    'energy_production',
    'fugitive',
    'residential',
    'waste',
    'commercial',
    'institutional',
    'municipal',
    'local_transport',
    'visitor_transport',
]
EMISSIONS_2016 = {
    'energy_production': 0,
    'fugitive': 7070,
    'residential': 36244,
    'waste': 16073,
    'commercial': 104412,
    'institutional': 10430,
    'municipal': 4598,
    'local_transport': 28689,
    'visitor_transport': 217563,
}
EMISSIONS_BAU_2050 = {
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
EMISSIONS_ROADMAP_2050 = {
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
PUBLISHED_TOTALS = {'2016': 425080, 'bau_2050': 292160, 'roadmap_2050': 71884}

# Building sectors whose business-as-usual change is taken to be complete by 2031, when
# the Alberta grid factor stops falling (Figure 12, p. 18) and building emissions level
# off (Figure 21, p. 25; text p. 23: commercial emissions "remain relatively constant
# after 2030").
BUILDING_SECTORS = ['residential', 'commercial', 'institutional', 'municipal']
BUILDING_BAU_COMPLETE_YEAR = 2031

# p. 103 by fuel source, t CO2e. Exact.
FUEL_SOURCES = [
    'fuel_oil',
    'fugitive',
    'natural_gas',
    'propane',
    'waste',
    'local_gasoline',
    'visitor_gasoline',
    'local_electricity',
    'visitor_electricity',
    'local_diesel',
    'visitor_diesel',
]
EMISSIONS_BY_FUEL = {  # (2016, BAU 2050, Roadmap 2050)
    'fuel_oil': (153, 116, 8),
    'fugitive': (7070, 6658, 2044),
    'natural_gas': (58687, 55266, 16966),
    'propane': (3854, 3235, 455),
    'waste': (16073, 16821, 4876),
    'local_gasoline': (13512, 10618, 0),
    'visitor_gasoline': (205960, 136200, 0),
    'local_electricity': (92126, 37343, 21461),
    'visitor_electricity': (884, 5208, 25863),
    'local_diesel': (15540, 11493, 90),
    'visitor_diesel': (11222, 9203, 120),
}

# p. 102: energy, GJ. Exact. (2016, BAU 2050, Roadmap 2050)
ENERGY_BY_SECTOR = {
    'residential': (443985, 471805, 298588),
    'commercial': (1007013, 960636, 737982),
    'institutional': (100594, 95961, 73719),
    'municipal': (44350, 42308, 32502),
    'local_transport': (415508, 320293, 90177),
    'visitor_transport': (3151004, 2164146, 537105),
}
ENERGY_BY_CARRIER = {
    'solar': (681, 5813, 154057),
    'other': (145620, 106456, 34455),
    'propane': (63006, 52894, 7440),
    'diesel': (373261, 288350, 2751),
    'gasoline': (3064416, 2051537, 0),
    'grid_renewable_electricity': (26597, 26597, 668900),
    'electricity': (305867, 409865, 307323),
    'natural_gas': (1180925, 1112089, 341420),
    'biogas': (0, 0, 127439),
    'district_energy': (0, 0, 126178),
    'fuel_oil': (2079, 1547, 108),
}

# ---------------------------------------------------------------------------
# Page ix: emissions removed by Roadmap action, kt CO2e. Exact.
# (in 2050, cumulative 2020-2050)
# ---------------------------------------------------------------------------
ACTION_TABLE = {
    '1 New home efficiency': (0.56, 8.16),
    '2 New non-residential building efficiency': (0.25, 8.59),
    '3 Residential retrofits': (8.01, 88.72),
    '4 Non-residential building retrofits': (19.04, 213.96),
    '5 Municipal building retrofits': (2.59, 67.89),
    '6 Recommissioning': (2.43, 47.11),
    '7, 8 Biogas and wood waste cogeneration': (11.52, 340.98),
    '9-12 Gas cogeneration': (16.43, 467.72),
    '13a Residential solar PV': (0.48, 8.67),
    '13b Commercial solar PV': (3.79, 68.08),
    '13c, 14 Parking lot and facilities solar PV': (3.19, 124.78),
    '15 Micro wind': (0.52, 19.16),
    '16 Wastewater plant heat recovery': (0.20, 6.25),
    '17a Home heat pumps': (0.75, 9.23),
    '17b Non-residential heat pumps': (11.41, 173.20),
    '18, 19 Renewable electricity storage and procurement': (15.89, 362.32),
    '20 Renewable natural gas procurement': (9.99, 193.42),
    '21-23 Enhanced transit': (27.92, 480.10),
    '24 Electrify transit': (0.00, 1.02),
    '25 Electrify Town fleet': (0.00, 0.06),
    '26a Electrify local vehicles': (4.24, 78.36),
    '26b Electrify visitor vehicles': (64.31, 1303.74),
    '27 Electrify commercial vehicles': (7.83, 160.51),
    '28 Create a carshare': (1.25, 22.75),
    '29 Congestion charge or car-free zones': (5.33, 196.70),
    '30 Cycling and walking programs': (2.35, 72.00),
}
ACTION_TABLE_TOTAL = (220.28, 4523.50)

# The five largest actions modelled one by one; everything else is one block.
MODELLED_ACTIONS = {
    'electrify_visitor_vehicles': '26b Electrify visitor vehicles',
    'enhanced_transit': '21-23 Enhanced transit',
    'non_residential_retrofits': '4 Non-residential building retrofits',
    'gas_cogeneration': '9-12 Gas cogeneration',
    'renewable_electricity_procurement': '18, 19 Renewable electricity storage and procurement',
}
OTHER_ACTION = 'other_roadmap_actions'

# p. 49: gas cogeneration is "responsible for 1.3% of Banff's emissions in 2050", which is
# the 956 t of 'fossil fuel energy production' on p. 103 (956 / 71,884 = 1.33%).
GAS_COGEN_OWN_EMISSIONS = EMISSIONS_ROADMAP_2050['energy_production']

# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------
# Residents: Table 3 (p. 11) gives 2016 and 2050; the visitor table embedded in the PDF
# text layer behind Figures 5 and 6 (p. 12) gives 2021, 2026 and 2031. That table starts
# from 9,521 rather than 9,511 (see DATA_NOTES.md).
RESIDENTS = {2016: 9511, 2021: 10049, 2026: 10562, 2031: 11103, 2050: 13546}
# Visitors per year, p. 12 table. 2050 day visitors read from Figure 6 (10.9 thousand
# average daily day visitors, times 365). Multi-day visitors flat to 2050 (text p. 12).
DAY_VISITORS = {2016: 1990733, 2021: 2198030, 2026: 2426520, 2031: 2679100, 2050: 10900 * 365}
MULTI_DAY_VISITORS = {2016: 3264770, 2021: 3264772, 2026: 3264772, 2031: 3264772, 2050: 3264772}
# Published visitor-adjusted population, p. 12 table and Figure 6 (2050, chart).
VISITOR_ADJUSTED_PUBLISHED = {2016: 23920, 2021: 25015, 2026: 26154, 2031: 27388, 2050: 33400}

# Floor area, m2, Table 3 (p. 11). Exact. The commercial cap is reached "in the next 2
# years" (p. 14, written 2019), so the 2050 commercial value is placed at 2021 too.
FLOOR_AREA = {
    'residential': {2016: 578229, 2050: 739232},
    'municipal': {2016: 25690, 2050: 25690},
    'non_residential': {2016: 249972, 2050: 249972},
    'commercial_hospitality': {2016: 333456, 2021: 343276, 2050: 343276},
    'institutional': {2016: 81330, 2050: 81330},
}

# Waste, t, Table 3 (p. 11). Exact.
WASTE = {
    'landfilled': {2016: 4093, 2050: 7428},
    'recycled': {2016: 1696, 2050: 2733},
    'biologically_treated': {2016: 2279, 2050: 3979},
}

# Alberta grid factor, g/kWh. 2016 and 2031 exact (Table 3, p. 11; text p. 18 says held
# constant after 2031). CO2 between 2016 and 2031 read from Figure 12 (p. 18). CH4 and N2O
# only have the two end points; the model interpolates between them.
GRID_CO2_FIG12 = {
    2016: 942,
    2017: 820,
    2018: 720,
    2019: 710,
    2020: 690,
    2021: 620,
    2022: 580,
    2023: 580,
    2024: 570,
    2025: 560,
    2026: 530,
    2027: 510,
    2028: 500,
    2029: 480,
    2030: 420,
    2031: 327,
    2050: 327,
}
GRID_CH4 = {2016: 0.06, 2031: 0.021, 2050: 0.021}
GRID_N2O = {2016: 0.02, 2031: 0.007, 2050: 0.007}
GWP_100 = {'co2': 1, 'ch4': 34, 'n2o': 298}  # Table 2, p. 9 (100-year)


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------


def ramp_cumulative(start: int, full: int) -> float:
    """Years-of-full-effect over 2020-2050 for a straight ramp from 0 at `start` to 1 at `full`."""
    total = 0.0
    for y in range(2020, 2051):
        if y <= start:
            share = 0.0
        elif y >= full:
            share = 1.0
        else:
            share = (y - start) / (full - start)
        total += share
    return total


def fit_ramp(annual_2050: float, cumulative: float) -> tuple[int, int, float]:
    """
    Choose whole start and full-effect years so the ramp's 2020-2050 total matches the table.

    The Roadmap gives each action's effect in 2050 and its total over 2020-2050 (p. ix).
    A straight ramp that starts in 2020 and reaches full effect in 2050 sums to 15.5 years
    of full effect. Actions with more than that are front-loaded: start in 2020 and reach
    full effect earlier. Actions with less start later and reach full effect in 2050.
    """
    target = cumulative / annual_2050
    candidates = [(2020, full) for full in range(2021, 2051)] + [(start, 2050) for start in range(2020, 2050)]
    best = min(candidates, key=lambda c: abs(ramp_cumulative(*c) - target))
    return best[0], best[1], ramp_cumulative(*best)


def allocate(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Split `total` over the keys in proportion to `weights`, as whole tonnes summing exactly to `total`."""
    wsum = sum(weights.values())
    raw = {k: total * w / wsum for k, w in weights.items()}
    out = {k: round(v) for k, v in raw.items()}
    diff = total - sum(out.values())
    if diff:
        largest = max(out, key=lambda k: abs(out[k]))
        out[largest] += diff
    return out


def action_allocations() -> dict[str, dict[str, int]]:
    """2050 emission change by action and sector, t CO2e/a (negative = reduction)."""
    kt = {a: round(ACTION_TABLE[label][0] * 1000) for a, label in MODELLED_ACTIONS.items()}

    # Electricity-supply actions displace grid electricity wherever it is used. The Roadmap
    # does not say where; we split them by the Roadmap 2050 electricity emissions it does
    # publish (p. 103): visitor electricity (EV charging) vs local electricity, and the
    # local part over the local sectors in proportion to their Roadmap 2050 emissions.
    local_sectors = [*BUILDING_SECTORS, 'local_transport']
    local_e = EMISSIONS_BY_FUEL['local_electricity'][2]
    visitor_e = EMISSIONS_BY_FUEL['visitor_electricity'][2]

    def electricity_split(total: int) -> dict[str, int]:
        first = allocate(total, {'visitor_transport': visitor_e, 'local': local_e})
        local = allocate(first['local'], {s: EMISSIONS_ROADMAP_2050[s] for s in local_sectors})
        return {'visitor_transport': first['visitor_transport'], **local}

    alloc: dict[str, dict[str, int]] = {}
    alloc['electrify_visitor_vehicles'] = {'visitor_transport': -kt['electrify_visitor_vehicles']}
    alloc['enhanced_transit'] = {
        s: -v
        for s, v in allocate(
            kt['enhanced_transit'],
            {s: EMISSIONS_BAU_2050[s] for s in ('local_transport', 'visitor_transport')},
        ).items()
    }
    alloc['non_residential_retrofits'] = {
        s: -v
        for s, v in allocate(
            kt['non_residential_retrofits'],
            {s: EMISSIONS_BAU_2050[s] for s in ('commercial', 'institutional')},
        ).items()
    }
    gross = kt['gas_cogeneration'] + GAS_COGEN_OWN_EMISSIONS
    alloc['gas_cogeneration'] = {
        'energy_production': GAS_COGEN_OWN_EMISSIONS,
        **{s: -v for s, v in electricity_split(gross).items()},
    }
    alloc['renewable_electricity_procurement'] = {
        s: -v for s, v in electricity_split(kt['renewable_electricity_procurement']).items()
    }

    # Everything else: whatever each sector still needs to get from BAU 2050 to Roadmap 2050.
    other = {}
    for s in SECTORS:
        needed = EMISSIONS_BAU_2050[s] - EMISSIONS_ROADMAP_2050[s]
        done = -sum(a.get(s, 0) for a in alloc.values())
        rest = needed - done
        if rest < 0:
            raise SystemExit(f'Allocation leaves a negative remainder in {s}: {rest}')
        if rest:
            other[s] = -rest
    alloc[OTHER_ACTION] = other
    return alloc


def action_ramps() -> dict[str, tuple[int, int, float, float]]:
    """Start year, full-effect year, fitted and published years-of-full-effect, per action."""
    out = {}
    for a, label in MODELLED_ACTIONS.items():
        annual, cum = ACTION_TABLE[label]
        start, full, fitted = fit_ramp(annual, cum)
        out[a] = (start, full, fitted, cum / annual)
    modelled_labels = set(MODELLED_ACTIONS.values())
    annual = sum(v[0] for k, v in ACTION_TABLE.items() if k not in modelled_labels)
    cum = sum(v[1] for k, v in ACTION_TABLE.items() if k not in modelled_labels)
    start, full, fitted = fit_ramp(annual, cum)
    out[OTHER_ACTION] = (start, full, fitted, cum / annual)
    return out


def bau_value(sector: str, year: int) -> float:
    """Business-as-usual emissions as the model builds them: 2016 inventory moved in a straight line to the goal."""
    e16, e50 = EMISSIONS_2016[sector], EMISSIONS_BAU_2050[sector]
    end = BUILDING_BAU_COMPLETE_YEAR if sector in BUILDING_SECTORS else 2050
    share = min(1.0, (year - 2016) / (end - 2016))
    return e16 + (e50 - e16) * share


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------

DIM_COLUMNS = [
    'sector',
    'roadmap_action',
    'fuel_source',
    'energy_carrier',
    'visitor_type',
    'building_type',
    'waste_treatment',
    'greenhouse_gas',
]
HEADER = ['Dataset', 'Metric', 'Quantity', 'Unit', *DIM_COLUMNS, *[str(y) for y in YEARS], 'Source', 'Comment']


def dense(points: dict[int, float], last: int | None = None) -> dict[int, float]:
    """
    Fill every year between the given points with a straight line.

    Written out here rather than left to the model's interpolation, because the model marks
    an interpolated year after a measured one as measured too. Writing the years out lets the
    dataset say plainly that only 2016 is measured.
    """
    years = sorted(points)
    out: dict[int, float] = {}
    for a, b in pairwise(years):
        for y in range(a, b):
            out[y] = points[a] + (points[b] - points[a]) * (y - a) / (b - a)
    out[years[-1]] = points[years[-1]]
    out = {y: (round(v) if abs(v) >= 100 else round(v, 4)) for y, v in out.items()}
    if last is not None:
        out = {y: v for y, v in out.items() if y <= last}
    return out


def row(dataset, metric, quantity, unit, values: dict[int, float | None], source, comment, **dims):
    r = dict.fromkeys(HEADER, '')
    r.update({'Dataset': dataset, 'Metric': metric, 'Quantity': quantity, 'Unit': unit, 'Source': source})
    r['Comment'] = comment
    for d, v in dims.items():
        assert d in DIM_COLUMNS, d
        r[d] = v
    for y, v in values.items():
        r[str(y)] = '' if v is None else (f'{v:g}' if isinstance(v, float) else str(v))
    return r


def build_rows() -> list[dict]:
    rows = []
    both = f'{ROADMAP}; {ASSUMPTION}'

    # Emissions inventory 2016 - the model's starting point.
    for s in SECTORS:
        rows.append(
            row(
                'Emissions inventory',
                'Emissions',
                'emissions',
                't_co2e/a',
                {2016: EMISSIONS_2016[s]},
                ROADMAP,
                'Appendix 2, p. 103, 2016 column. Exact.' + (' Shown as "-" (none) in 2016.' if s == 'energy_production' else ''),
                sector=s,
            )
        )

    # Business-as-usual goal: what the "happens regardless" changes move emissions to.
    for s in SECTORS:
        vals = {2050: EMISSIONS_BAU_2050[s]}
        comment = 'Appendix 2, p. 103, BAU 2050 column. Exact.'
        src = ROADMAP
        if s in BUILDING_SECTORS:
            vals[BUILDING_BAU_COMPLETE_YEAR] = EMISSIONS_BAU_2050[s]
            comment += (
                ' The 2031 value repeats the 2050 value: assumption that the building change is complete when the'
                ' Alberta grid factor stops falling in 2031 (Figure 12, p. 18) and building emissions level off'
                ' (Figure 21, p. 25).'
            )
            src = both
        if s == 'energy_production':
            comment += ' Blank in the report, read as zero.'
        rows.append(row('Emissions business as usual', 'Emissions', 'emissions', 't_co2e/a', vals, src, comment, sector=s))

    # Roadmap 2050 as published, for the comparison node.
    for s in SECTORS:
        rows.append(
            row(
                'Emissions Roadmap published',
                'Emissions',
                'emissions',
                't_co2e/a',
                {2050: EMISSIONS_ROADMAP_2050[s]},
                ROADMAP,
                'Appendix 2, p. 103, Roadmap 2050 column. Exact. Used only to check the model.',
                sector=s,
            )
        )

    # 2016 vs 2026 reconciliation, emissions. 2026 is a placeholder.
    for s in SECTORS:
        v26 = round(bau_value(s, 2026))
        rows.append(
            row(
                'Inventory reconciliation',
                'Emissions',
                'emissions',
                't_co2e/a',
                dense({2016: EMISSIONS_2016[s], 2026: v26}),
                f'{ROADMAP}; {PLACEHOLDER}',
                '2016: Appendix 2, p. 103, exact. 2026: PLACEHOLDER, not measured. It is the 2019 Roadmap business-as-usual'
                ' forecast for 2026 as this model builds it (straight line from 2016 to the 2050 value, to 2031 for'
                ' buildings). 2017-2025: interpolated (straight line) in this file. Replace 2026 with the 2026 GPC BASIC'
                ' inventory.',
                sector=s,
            )
        )

    # Emissions by fuel source (display).
    for f in FUEL_SOURCES:
        e16, e50, _ = EMISSIONS_BY_FUEL[f]
        rows.append(
            row(
                'Emissions by fuel source',
                'Emissions',
                'emissions',
                't_co2e/a',
                dense({2016: e16, 2050: e50}),
                ROADMAP,
                'Appendix 2, p. 103, 2016 and BAU 2050 columns. Exact.'
                ' Years between: interpolated (straight line) in this file.'
                f' Roadmap 2050 value: {EMISSIONS_BY_FUEL[f][2]} t.',
                fuel_source=f,
            )
        )

    # Energy (display).
    for s, (e16, e50, r50) in ENERGY_BY_SECTOR.items():
        rows.append(
            row(
                'Energy use by sector',
                'Energy use',
                'energy',
                'GJ/a',
                dense({2016: e16, 2050: e50}),
                ROADMAP,
                f'Appendix 2, p. 102, 2016 and BAU 2050 columns. Exact.'
                ' Years between: interpolated (straight line) in this file.'
                f' Roadmap 2050 value: {r50:,} GJ.',
                sector=s,
            )
        )
    for c, (e16, e50, r50) in ENERGY_BY_CARRIER.items():
        rows.append(
            row(
                'Energy use by fuel',
                'Energy use',
                'energy',
                'GJ/a',
                dense({2016: e16, 2050: e50}),
                ROADMAP,
                f'Appendix 2, p. 102, 2016 and BAU 2050 columns. Exact.'
                ' Years between: interpolated (straight line) in this file.'
                f' Roadmap 2050 value: {r50:,} GJ.',
                energy_carrier=c,
            )
        )

    # Residents.
    rows.append(
        row(
            'Residents',
            'Residents',
            'population',
            'cap',
            dense(RESIDENTS),
            ROADMAP,
            '2016 and 2050: Table 3, p. 11, exact. 2021, 2026, 2031: visitor table in the PDF text layer behind'
            ' Figures 5-6, p. 12, exact (that table uses 9,521 for 2016).'
            ' Other years: interpolated (straight line) in this file.',
        )
    )

    # Visitors.
    rows.append(
        row(
            'Visitors',
            'Visitors',
            'population',
            'cap/a',
            dense(DAY_VISITORS),
            ROADMAP,
            '2016-2031: visitor table, p. 12, exact. 2050: read from chart (Figure 6, p. 12: 10.9 thousand average'
            ' daily day visitors, times 365). Other years: interpolated (straight line) in this file.',
            visitor_type='day_visitor',
        )
    )
    rows.append(
        row(
            'Visitors',
            'Visitors',
            'population',
            'cap/a',
            dense(MULTI_DAY_VISITORS),
            ROADMAP,
            '2016-2031: visitor table, p. 12, exact (3,264,770 in 2016, 3,264,772 after). 2050: held flat, as the text'
            ' on p. 12 says multi-day visitors do not increase substantially.',
            visitor_type='multi_day_visitor',
        )
    )
    rows.append(
        row(
            'Visitor presence',
            'Presence per visit',
            'duration',
            'd',
            {2016: 1},
            both,
            'The text on p. 12 says visitors are multiplied by an average stay of 2.5 days and divided by 365. The'
            ' published visitor-adjusted populations (23,920 in 2016, 26,154 in 2026) are only reproduced with 1 day'
            ' per counted visit, so 1 day is used. See DATA_NOTES.md.',
        )
    )

    # Floor area.
    for b, vals in FLOOR_AREA.items():
        comment = 'Table 3, p. 11, 2016 and 2050. Exact. Years between: interpolated (straight line) in this file.'
        src = ROADMAP
        if b == 'commercial_hospitality':
            comment += ' The 2021 value repeats 2050: the cap is reached "in the next 2 years" (p. 14, written in 2019).'
            src = both
        rows.append(row('Floor area', 'Floor area', 'floor_area', 'm**2', dense(vals), src, comment, building_type=b))

    # Waste.
    for w, vals in WASTE.items():
        rows.append(
            row(
                'Waste tonnage',
                'Waste',
                'mass',
                't/a',
                dense(vals),
                ROADMAP,
                'Table 3, p. 11, 2016 and 2050. Exact. Years between: interpolated (straight line) in this file.',
                waste_treatment=w,
            )
        )

    # Grid factor.
    rows.append(
        row(
            'Grid emission factor',
            'Emission factor',
            'emission_factor',
            'g/kWh',
            dense(GRID_CO2_FIG12),
            ROADMAP,
            '2016 (942) and 2031 (327): Table 3, p. 11, exact. 2017-2030: read from chart (Figure 12, p. 18).'
            ' 2032-2050: held at the 2031 value (p. 18).',
            greenhouse_gas='co2',
        )
    )
    rows.append(
        row(
            'Grid emission factor',
            'Emission factor',
            'emission_factor',
            'g/kWh',
            dense(GRID_CH4),
            ROADMAP,
            'Table 3, p. 11, 2016 and 2050 (reached 2031, p. 18). Exact.'
            ' Years between: interpolated (straight line) in this file.',
            greenhouse_gas='ch4',
        )
    )
    rows.append(
        row(
            'Grid emission factor',
            'Emission factor',
            'emission_factor',
            'g/kWh',
            dense(GRID_N2O),
            ROADMAP,
            'Table 3, p. 11, 2016 and 2050 (reached 2031, p. 18). Exact.'
            ' Years between: interpolated (straight line) in this file.',
            greenhouse_gas='n2o',
        )
    )
    for g, v in GWP_100.items():
        rows.append(
            row(
                'Global warming potential',
                'GWP',
                'ratio',
                't_co2e/t',
                {2016: v},
                ROADMAP,
                'Table 2, p. 9, 100-year values. Exact.',
                greenhouse_gas=g,
            )
        )

    # Action effects.
    alloc = action_allocations()
    ramps = action_ramps()
    for a, by_sector in alloc.items():
        start, full, fitted, published = ramps[a]
        label = MODELLED_ACTIONS.get(a, 'the other 21 rows of the p. ix table')
        for s, v in by_sector.items():
            vals = {start: 0, full: v}
            if full < 2050:
                vals[2050] = v
            if a == OTHER_ACTION:
                how = (
                    "Remainder: the sector's BAU 2050 minus Roadmap 2050 (p. 103), less what the five modelled"
                    ' actions take from it.'
                )
            elif a == 'electrify_visitor_vehicles':
                how = 'All of it is visitor transport.'
            elif a in ('enhanced_transit', 'non_residential_retrofits'):
                how = 'Split over the sectors it acts on in proportion to their BAU 2050 emissions (p. 103).'
            elif s == 'energy_production':
                how = "The cogeneration plants' own gas emissions, 956 t (p. 103 and p. 49), added."
            else:
                how = (
                    'Split by where grid electricity is still used in Roadmap 2050: visitor vs local electricity'
                    ' emissions (p. 103), then the local part over local sectors in proportion to their Roadmap'
                    ' 2050 emissions.'
                )
            rows.append(
                row(
                    'Roadmap action effects',
                    'Emission change',
                    'emissions',
                    't_co2e/a',
                    vals,
                    both,
                    f'Effect in 2050 from p. ix ({label}). Sector allocation is a demo assumption: {how}'
                    f' Timing: straight line from 0 in {start} to full effect in {full}, chosen so that the 2020-2050'
                    f' total matches p. ix ({fitted:.1f} vs {published:.1f} years of full effect). Interdependent with'
                    ' the other actions (p. 54); not an independent saving.',
                    sector=s,
                    roadmap_action=a,
                )
            )
    return rows


TEMPLATE_INDICATORS = [
    # (metric, quantity, unit, 2016 value or None, 2016 note)
    ('Buildings', 'number', 'dimensionless', None, 'Not in the Roadmap (Figure 9 is a map, not a count).'),
    ('Employment', 'employment', 'cap', 5100, 'Read from chart (Figure 5, p. 12).'),
    ('Households', 'number', 'dimensionless', 2500, 'Read from chart (Figure 5, p. 12).'),
    ('Transit ridership', 'number', 'dimensionless', None, 'Not in the Roadmap. Annual boardings, Roam Transit.'),
    ('Tourism revenue', 'currency', 'CAD/a', None, 'Not in the Roadmap. Needed for emissions per tourism dollar.'),
    (
        'Gross domestic product',
        'currency',
        'CAD/a',
        None,
        'Not in the Roadmap. Needed for emissions per unit of economic output.',
    ),
    (
        'Air travel emissions',
        'emissions',
        't_co2e/a',
        None,
        'Outside the Roadmap inventory (scope 3, p. 13). Reference-only estimate.',
    ),
]


def build_template_rows() -> list[dict]:
    rows = []
    for metric, quantity, unit, v16, note in TEMPLATE_INDICATORS:
        src = ROADMAP if v16 is not None else PLACEHOLDER
        r = row(
            'Reconciliation indicators',
            metric,
            quantity,
            unit,
            {2016: v16, 2026: None},
            src,
            f'2016: {note} 2026: blank on purpose - to be collected for the 2026 inventory.',
        )
        rows.append(r)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    used_dims = [d for d in DIM_COLUMNS if any(r[d] for r in rows)]
    used_years = [str(y) for y in YEARS if any(r[str(y)] != '' for r in rows)] or ['2016', '2026']
    if path.name.startswith('banff_demo_template'):
        used_years = ['2016', '2026']
    header = ['Dataset', 'Metric', 'Quantity', 'Unit', *used_dims, *used_years, 'Source', 'Comment']
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def write_sources(path: Path) -> None:
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Name', 'Authority', 'URL', 'Description', 'Edition', 'Target'])
        w.writerow([
            ROADMAP,
            'Town of Banff',
            '',
            (
                'Town of Banff, Renewable Energy Transition Roadmap (analysis by Sustainability Solutions Group and'
                ' whatIf? Technologies, funded by the Federation of Canadian Municipalities). Page numbers are the'
                f' printed report page numbers. {DEMO_NOTICE}'
            ),
            'December 2019',
            'data_point',
        ])
        w.writerow([
            ASSUMPTION,
            'Kausal',
            '',
            (
                'An assumption or calculation made by Kausal for this demo, not a figure in the Roadmap. The rule is'
                f' in the data point comment and in DATA_NOTES.md. {DEMO_NOTICE}'
            ),
            '2026-11',
            'data_point',
        ])
        w.writerow([
            PLACEHOLDER,
            'Kausal',
            '',
            f'Placeholder for the 2026 inventory. Not measured. To be replaced by the 2026 GPC BASIC inventory. {DEMO_NOTICE}',
            '2026-11',
            'data_point',
        ])


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check() -> list[str]:
    """Reconcile against the published totals. Returns findings; raises on extraction defects."""
    findings = []
    t16 = sum(EMISSIONS_2016.values())
    tb = sum(EMISSIONS_BAU_2050.values())
    tr = sum(EMISSIONS_ROADMAP_2050.values())
    for name, got, pub in (
        ('2016', t16, PUBLISHED_TOTALS['2016']),
        ('BAU 2050', tb, PUBLISHED_TOTALS['bau_2050']),
        ('Roadmap 2050', tr, PUBLISHED_TOTALS['roadmap_2050']),
    ):
        if abs(got - pub) > 5:
            raise SystemExit(f'DEFECT: {name} sector total {got} vs published {pub}')
        findings.append(f'{name}: sectors sum to {got:,} t, published total {pub:,} t (difference {got - pub:+}).')
    for i, name in enumerate(('2016', 'BAU 2050', 'Roadmap 2050')):
        fuel = sum(v[i] for v in EMISSIONS_BY_FUEL.values())
        findings.append(f'{name}: fuel sources sum to {fuel:,} t.')
    alloc = action_allocations()
    total = -sum(sum(v.values()) for v in alloc.values())
    findings.append(
        f'Actions in 2050 sum to {total:,} t; BAU 2050 minus Roadmap 2050 (sector sums) is {tb - tr:,} t;'
        f' page ix total is {ACTION_TABLE_TOTAL[0] * 1000:,.0f} t.'
    )
    if total != tb - tr:
        raise SystemExit('DEFECT: action allocation does not close')
    table_sum = sum(v[0] for v in ACTION_TABLE.values())
    findings.append(f'Page ix rows sum to {table_sum:.2f} kt (printed total {ACTION_TABLE_TOTAL[0]} kt).')
    for a, label in MODELLED_ACTIONS.items():
        got = -sum(alloc[a].values())
        if a == 'gas_cogeneration':
            got = -sum(alloc[a].values())
        if got != round(ACTION_TABLE[label][0] * 1000):
            raise SystemExit(f'DEFECT: {a} allocation {got} vs table')
    for y, pub in VISITOR_ADJUSTED_PUBLISHED.items():
        res = RESIDENTS[y]
        calc = res + (DAY_VISITORS[y] + MULTI_DAY_VISITORS[y]) / 365
        findings.append(f'Visitor-adjusted population {y}: residents + visitors/365 = {calc:,.0f} (published {pub:,}).')
    return findings


def main() -> None:
    findings = check()
    write_csv(HERE / 'banff_demo_data.csv', build_rows())
    write_csv(HERE / 'banff_demo_template_2026.csv', build_template_rows())
    write_sources(HERE / 'banff_demo_sources.csv')
    print('Wrote banff_demo_data.csv, banff_demo_template_2026.csv, banff_demo_sources.csv')
    print('\nChecks:')
    for f in findings:
        print(' -', f)
    print('\nAction allocation (t CO2e/a in 2050) and timing:')
    ramps = action_ramps()
    for a, by_sector in action_allocations().items():
        s, f, fitted, pub = ramps[a]
        print(f' {a}: ramp {s}->{f} ({fitted:.1f} vs {pub:.1f})', by_sector)
    print(
        '\n2026 placeholder (BAU):',
        {s: round(bau_value(s, 2026)) for s in SECTORS},
        'total',
        round(sum(bau_value(s, 2026) for s in SECTORS)),
    )


if __name__ == '__main__':
    sys.exit(main())
