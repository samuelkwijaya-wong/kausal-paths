# Banff demo - reconciliation check

Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap. Not prepared or endorsed by the Town of Banff.

Written by `configs/banff-demo/check_banff_demo.py`, which runs the model from the dataset CSVs and compares it with the Roadmap's published figures. Tolerance is 5 t for totals and 1 t for sectors. The 2016 and BAU 2050 totals are 1 t off because the published sector values themselves sum to 425,079 and 292,161; the action total is 3 t under the printed 220.28 kt for the same reason.

Roadmap 2050 as published (node): 71,884 t; years in node: [2050].

## Totals

| Check | Published | Model | Difference | Result |
|---|---:|---:|---:|---|
| 2016 inventory total | 425,080 | 425,079 | -1 | OK |
| Business as usual 2050 total | 292,160 | 292,161 | +1 | OK |
| Roadmap 2050 total | 71,884 | 71,884 | +0 | OK |
| Actions total in 2050 (BAU minus Roadmap) | 220,280 | 220,277 | -3 | OK |
| Baseline (no change) 2050 equals 2016 | 425,080 | 425,079 | -1 | OK |

## By sector, 2050

| Check | Published | Model | Difference | Result |
|---|---:|---:|---:|---|
| BAU 2050, energy_production | 0 | 0 | +0 | OK |
| BAU 2050, fugitive | 6,658 | 6,658 | +0 | OK |
| BAU 2050, residential | 26,882 | 26,882 | +0 | OK |
| BAU 2050, waste | 16,821 | 16,821 | +0 | OK |
| BAU 2050, commercial | 60,104 | 60,104 | +0 | OK |
| BAU 2050, institutional | 6,004 | 6,004 | +0 | OK |
| BAU 2050, municipal | 2,647 | 2,647 | +0 | OK |
| BAU 2050, local_transport | 22,381 | 22,381 | +0 | OK |
| BAU 2050, visitor_transport | 150,664 | 150,664 | +0 | OK |
| Roadmap 2050, energy_production | 956 | 956 | +0 | OK |
| Roadmap 2050, fugitive | 2,044 | 2,044 | +0 | OK |
| Roadmap 2050, residential | 11,324 | 11,324 | +0 | OK |
| Roadmap 2050, waste | 4,876 | 4,876 | +0 | OK |
| Roadmap 2050, commercial | 19,408 | 19,408 | +0 | OK |
| Roadmap 2050, institutional | 1,939 | 1,939 | +0 | OK |
| Roadmap 2050, municipal | 855 | 855 | +0 | OK |
| Roadmap 2050, local_transport | 4,382 | 4,382 | +0 | OK |
| Roadmap 2050, visitor_transport | 26,100 | 26,100 | +0 | OK |

## The five modelled actions, effect in 2050 (switching each off in the Roadmap scenario)

| Check | Published | Model | Difference | Result |
|---|---:|---:|---:|---|
| electrify_visitor_vehicles | 64,310 | 64,310 | +0 | OK |
| enhanced_transit | 27,920 | 27,920 | +0 | OK |
| non_residential_retrofits | 19,040 | 19,040 | +0 | OK |
| gas_cogeneration | 16,430 | 16,430 | +0 | OK |
| renewable_electricity_procurement | 15,890 | 15,890 | +0 | OK |

## Path, total t CO2e

| Year | No change | Business as usual | Roadmap |
|---|---:|---:|---:|
| 2016 | 425,079 | 425,079 | 425,079 |
| 2020 | 425,079 | 400,493 | 400,493 |
| 2025 | 425,079 | 369,761 | 304,232 |
| 2026 | 425,079 | 363,615 | 288,266 |
| 2030 | 425,079 | 339,029 | 223,494 |
| 2031 | 425,079 | 332,883 | 206,621 |
| 2035 | 425,079 | 324,310 | 155,141 |
| 2040 | 425,079 | 313,594 | 109,622 |
| 2045 | 425,079 | 302,877 | 89,202 |
| 2050 | 425,079 | 292,161 | 71,884 |

## Efficiency measures, Roadmap scenario

| Year | t per resident | t per visitor-adjusted person | kg per visit (visitor transport) |
|---|---:|---:|---:|
| 2016 | 44.7 | 17.8 | 41.4 |
| 2026 | 27.3 | 11.0 | 27.0 |
| 2030 | 20.3 | 8.2 | 20.9 |
| 2050 | 5.3 | 2.2 | 3.6 |

## 2026 placeholder against the model's business as usual in 2026

| Check | Model BAU 2026 | Placeholder 2026 | Difference | Result |
|---|---:|---:|---:|---|
| 2026 placeholder, energy_production | 0 | 0 | +0 | OK |
| 2026 placeholder, fugitive | 6,949 | 6,949 | +0 | OK |
| 2026 placeholder, residential | 30,003 | 30,003 | +0 | OK |
| 2026 placeholder, waste | 16,293 | 16,293 | +0 | OK |
| 2026 placeholder, commercial | 74,873 | 74,873 | -0 | OK |
| 2026 placeholder, institutional | 7,479 | 7,479 | -0 | OK |
| 2026 placeholder, municipal | 3,297 | 3,297 | -0 | OK |
| 2026 placeholder, local_transport | 26,834 | 26,834 | +0 | OK |
| 2026 placeholder, visitor_transport | 197,887 | 197,887 | +0 | OK |

## Visitor-adjusted population

| Check | Published | Model | Difference | Result |
|---|---:|---:|---:|---|
| Visitor-adjusted population 2016 | 23,920 | 23,900 | -20 | OK |
| Visitor-adjusted population 2021 | 25,015 | 25,005 | -10 | OK |
| Visitor-adjusted population 2026 | 26,154 | 26,144 | -10 | OK |
| Visitor-adjusted population 2031 | 27,388 | 27,376 | -12 | OK |
| Visitor-adjusted population 2050 | 33,400 | 33,377 | -23 | OK |

Grid factor, g CO2e/kWh: 2016 950.0, 2026 534.5, 2031 329.8, 2050 329.8.
