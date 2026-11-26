# Banff demo - data notes

Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap.
Not prepared or endorsed by the Town of Banff.

Source: Town of Banff, *Renewable Energy Transition Roadmap*, December 2019 (analysis by
Sustainability Solutions Group and whatIf? Technologies, funded by the Federation of Canadian
Municipalities). Page numbers are the printed report page numbers. No other Town data is used.

This file lists every assumption and simplification in the demo, and the places where the
Roadmap disagrees with itself. Each data point also carries its own note (page, and whether it
is exact, read from a chart or interpolated) in the dataset `Comment` column.

## 1. Datasets

All datasets are in `banff_demo_data.csv` and are produced by `make_banff_demo_data.py`.

| Dataset (`banff-demo/...`) | What | Source | Exact, chart or interpolated |
|---|---|---|---|
| `emissions_inventory` | 2016 emissions by GPC sector | Appendix 2, p. 103 | Exact |
| `emissions_business_as_usual` | BAU 2050 emissions by sector (the target of the "happens regardless" actions) | p. 103 | 2050 exact; the 2031 building values repeat 2050 (assumption A2) |
| `emissions_roadmap_published` | Roadmap 2050 emissions by sector, for checking | p. 103 | Exact |
| `inventory_reconciliation` | 2016 and 2026 emissions by sector | p. 103 | 2016 exact; 2026 **placeholder** (A10); 2017-2025 interpolated |
| `emissions_by_fuel_source` | Emissions by fuel, 2016 and BAU 2050 | p. 103 | 2016 and 2050 exact; years between interpolated |
| `energy_use_by_sector`, `energy_use_by_fuel` | Energy, 2016 and BAU 2050 | p. 102 | 2016 and 2050 exact; years between interpolated; Roadmap 2050 values in the comments |
| `residents` | Permanent residents | Table 3, p. 11; visitor table p. 12 | 2016, 2021, 2026, 2031, 2050 exact; years between interpolated |
| `visitors` | Day and multi-day visitors per year | visitor table p. 12; Figure 6 | 2016-2031 exact; day visitors 2050 read from chart; years between interpolated |
| `visitor_presence` | Time each counted visit adds to the population: 1 day | derived from p. 12 | Assumption (A6) |
| `floor_area` | Floor area by building type | Table 3, p. 11 | 2016 and 2050 exact; commercial cap year from p. 14 (A8); years between interpolated |
| `waste_tonnage` | Landfilled, recycled, biologically treated | Table 3, p. 11 | 2016 and 2050 exact; years between interpolated |
| `grid_emission_factor` | Alberta grid factor, CO2, CH4, N2O | Table 3, p. 11; Figure 12, p. 18 | 2016 and 2031 exact; CO2 2017-2030 read from chart; CH4 and N2O interpolated; held after 2031 |
| `global_warming_potential` | CH4 34, N2O 298 (100-year) | Table 2, p. 9 | Exact |
| `roadmap_action_effects` | Emission change by action and sector | p. ix | 2050 totals exact; sector split and timing are assumptions (A3, A4, A5) |

`banff_demo_template_2026.csv` holds `banff-demo/reconciliation_indicators`: the RFP's
reconciliation items the Roadmap has no figure for (building count, transit ridership, tourism
revenue, economic output, air travel). Their 2026 cells are blank on purpose. Employment and
households have 2016 values read from Figure 5.

## 2. How the model is built

The demo is calibrated to the Roadmap's published results, not rebuilt from physics. It does
not model the building stock, vehicle fleets, energy flows or costs.

- Emissions start from the 2016 inventory by GPC sector, held flat.
- **(a) Happens regardless of local action**: three actions move each sector to the Roadmap's
  business-as-usual 2050 value. Together they *are* business as usual.
- **(b) Necessary local actions** and **(c) choices to weigh**: the five largest Roadmap
  actions, each with its 2050 effect from p. ix.
- **Other Roadmap actions**: one block for the other 21 rows of the p. ix action table.
- Scenarios: "No change from 2016" (reference line), "Business as usual" ((a) on) and
  "Roadmap" (everything on).

## 3. Assumptions and simplifications

**A1. Calibration, not physics.** Each action's 2050 effect is taken from the p. ix table. The
Roadmap says the actions are interdependent and the wedge chart shows only their combined effect
(p. 54), so an action switched off alone in the demo is an approximation, not the Roadmap's own
result. Energy use is shown for business as usual only; the demo does not say how each action
changes energy use.

**A2. Shape of business as usual.** Building emissions reach their 2050 BAU value by 2031, when
the Alberta grid factor stops falling (Figure 12) and building emissions level off (Figure 21;
p. 23: commercial emissions "remain relatively constant after 2030"). Transport, waste and
fugitive emissions move in a straight line from 2016 to 2050. The result follows the Roadmap's
BAU chart (Figure 17) within about 3%: 400 kt in 2020 (chart about 397), 364 kt in 2026 (about
368), 333 kt in 2031 (about 332), 314 kt in 2040 (about 304).

**A3. Which sectors each action reduces.** The Roadmap gives each action's total only.
- Electrify visitor vehicles: all in visitor transport.
- Enhanced transit: local and visitor transport, in proportion to their BAU 2050 emissions.
- Non-residential retrofits: commercial and institutional, in proportion to their BAU 2050 emissions.
- Gas cogeneration and renewable electricity procurement displace grid electricity. They are
  split by where grid electricity is still used in Roadmap 2050 (p. 103: visitor electricity
  25,863 t, local electricity 21,461 t), and the local part over the local sectors in proportion
  to their Roadmap 2050 emissions. Electric vehicle charging is why part of these actions lands in
  transport.
- Gas cogeneration also *adds* its own 956 t of gas emissions as "fossil fuel energy production"
  (p. 103; p. 49 says cogeneration is 1.3% of 2050 emissions, and 956 / 71,884 = 1.3%). Its net
  effect stays 16,430 t.

These rules are a demo device. The split is done in the producer script; a later version
should carry the published totals and do the split in the model.

**A4. Timing of each action.** p. ix gives each action's effect in 2050 and its total over
2020-2050. The demo uses a straight ramp from zero, with start and end years chosen so that the
2020-2050 total matches p. ix:

| Action | Ramp | 2020-2050 total, demo vs p. ix (years of full effect) |
|---|---|---|
| Electrify visitor vehicles | 2020 to 2040 | 20.5 vs 20.3 |
| Enhanced transit | 2020 to 2047 | 17.0 vs 17.2 |
| Non-residential retrofits | 2029 to 2050 | 11.0 vs 11.2 |
| Gas cogeneration | 2020 to 2024 | 28.5 vs 28.5 |
| Renewable electricity procurement | 2020 to 2035 | 23.0 vs 22.8 |
| Other actions (21 rows) | 2020 to 2037 | 22.0 vs 22.1 |

The visitor vehicle ramp ending in 2040 agrees with the Roadmap's statement that internal
combustion engines are effectively gone by 2040 (p. 56). The Roadmap path this gives is 223 kt
in 2030 and 110 kt in 2040; Figure 35 shows about 235 kt and 92 kt.

**A5. The "other actions" block** carries, sector by sector, whatever is left between BAU 2050
and Roadmap 2050 after the five modelled actions. It totals 76,686 t against 76,690 t from the
p. ix rows; the 4 t gap is rounding in the published sector values.

**A6. Visitor-adjusted population.** The text (p. 12) says visitors are multiplied by an average
stay of 2.5 days and divided by 365. The published values (23,920 in 2016, 26,154 in 2026,
27,388 in 2031) are reproduced only with one day per counted visit, i.e. residents plus all
visits divided by 365. The demo uses one day. It comes out 10-23 people below the published
values because Paths counts a year as 365.25 days and because of the 9,511 / 9,521 mismatch.

**A7. Day visitors in 2050** are read from Figure 6 (10.9 thousand average daily day visitors,
times 365 = 3.98 million a year), which agrees with the text ("roughly double"). The chart's last
axis label reads 2051; it is taken as 2050.

**A8. Commercial floor area.** Table 3 gives 2016 and 2050. The cap is reached "in the next 2
years" (p. 14, written in 2019), so the 2050 value is used from 2021.

**A9. Grid factor.** CO2 for 2017-2030 is read from Figure 12. CH4 and N2O have only the 2016
and 2031 values, with a straight line between. The combined factor is 950 g CO2e/kWh in 2016 and
330 from 2031. The demo shows the grid factor as a driver; it does not calculate electricity
emissions from it (the Roadmap does not publish electricity use by sector).

**A10. The 2026 column is a placeholder.** It is the Roadmap's business-as-usual forecast for
2026 as this model builds it (A2): 363,615 t in total. It is not a measurement, says so in every
data point, and is marked as a forecast. Population and visitor values for 2026 are the
Roadmap's own exact forecasts. When the 2026 GPC BASIC inventory exists, it replaces this
column.

**A11. Years between published points** are written into the datasets as straight lines, with a
note. Left to the model, Paths would interpolate them too, but would mark them as measured
rather than forecast.

**A12. The three-way action classification** ((a) happens regardless, (b) necessary local
actions, (c) choices to weigh) is Kausal's illustrative proposal for discussion with CEA. It is
not in the Roadmap and the Town has not seen it. Renewable electricity procurement is placed
under (c) because it competes with local generation.

**A13. Target.** The goal line is 30% below 2016 by 2030 and 80% below 2016 by 2050, as in the
brief and the RFP (see I2 below).

**A14. Blank cells.** "Fossil fuel energy production" is "-" in 2016 and blank in BAU 2050
(p. 103); both are read as zero.

**A15. Efficiency measures.** Emissions per resident, per visitor-adjusted person, and visitor
transport emissions per visit. "Per tourism dollar" and "per unit of economic output" are not
calculated, because the Roadmap has no tourism revenue or economic output data; both are rows
in the 2026 template.

**A16. Air travel** is outside the Roadmap inventory (scope 3, p. 13). It is not in the model;
the 2026 template has a reference-only row for it.

## 4. Where the Roadmap disagrees with itself

Kept as published. None of them changes the demo's emissions totals.

**I1. Renewable share of energy in 2050**: 54% (executive summary p. xi, and p. 67) versus about
48% (p. 55).

**I2. Baseline year of the 80% target**: "80% of 2005 levels" (executive summary p. xi) versus
2016 everywhere else and in the RFP. p. 7 explains that 2005 data were inadequate, so the
Roadmap uses 2016 as the baseline instead.

**I3. Roadmap total energy in 2050**: 1,770,073 GJ (Appendix 2, p. 102), 1,545,076 GJ (p. viii)
and 1.47 million GJ (Figure B, p. xiii).

**I4. Total energy in 2016**: 5,161,772 GJ (p. viii) versus 5,162,454 GJ (p. 102 by sector) and
5,162,452 GJ (p. 102 by fuel).

**I5. Residents in 2016**: 9,511 (Table 3, p. viii) versus 9,521 (visitor table, p. 12).

**I6. Municipal building retrofits complete**: 2030 (Table 4, p. 30) versus 2035 (Action 5
blueprint, p. 75).

**I7. Visitor transportation share of 2016 emissions**: 51% (217,563 of 425,080; Figure A) versus
58% in the text on p. 23, which appears to combine visitor and local transport (58.0%).

**I8. Average visitor stay** (new): the text says 2.5 days, the published numbers use 1 day (A6).

**I9. Multi-day visitors** (new): 3,264,770 in 2016 and 3,264,772 from 2021 in the same table.

**I10. Totals and rows** (new): the sector rows sum to 425,079 (2016) and 292,161 (BAU 2050)
against published totals of 425,080 and 292,160; the fuel rows sum to 425,081 (2016) and
71,883 (Roadmap 2050). The action rows on p. ix sum to the printed 220.28 kt, while BAU minus
Roadmap by sector is 220,277 t. All rounding.

**I11. Figure 20 axis** (new): labelled "kilotonnes CO2e" with values up to 0.3; the figures are
megatonnes (0.25 Mt = 250 kt).

**I12. The visitor table** (new) that gives residents and visitors for 2021, 2026 and 2031 is in
the PDF's text layer behind Figures 5 and 6 (p. 12) and is not visible on the printed page. It is
consistent with the charts.
