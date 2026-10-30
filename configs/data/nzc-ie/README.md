# nzc-ie demo data (Dublin City)

Demo datasets for `configs/nzc-ie.yaml` (NetZeroPlanner with the Irish LACAP layer) and
`configs/ie-lacap-dublin.yaml` (the Irish layer on its own). Proof of concept for Cork City
Council, Dublin City Council and NetZeroCities. **Not an official inventory.**

Each CSV file is one dataset in the upload format of
[`docs/dataset-csv-format.md`](../../../docs/dataset-csv-format.md). Every row has a `Source`
(a name in `sources.csv`) and a `Comment` saying where the number comes from: a printed page of
the Dublin City Council Climate Action Plan 2024–2029, or how it was estimated.

## Files

| File | Dataset id | What it holds |
|---|---|---|
| `energy_inventory.csv` | `nzc-ie/energy_inventory` | Energy use in 2018 by LACAP sector and energy carrier (MWh/a) |
| `direct_emissions.csv` | `nzc-ie/direct_emissions` | Non-energy emissions in 2018: waste and wastewater, F-gases, industrial processes, agriculture, LULUCF (t/a) |
| `emission_factors.csv` | `nzc-ie/emission_factors` | Fuel factors and the national grid CO2 path (t/MWh) |
| `energy_industries.csv` | `nzc-ie/energy_industries` | LACAP Step 1: emissions at power/heat plants in the city (shown, not added) |
| `council_operations.csv` | `nzc-ie/council_operations` | Council's own emissions 2018 and 2021 by energy carrier |
| `population.csv` | `nzc-ie/population` | Population (census and projection) |
| `action_targets.csv` | `nzc-ie/action_targets` | KPI path for each action (homes, buildings, MWp, shares) |
| `action_unit_impacts.csv` | `nzc-ie/action_unit_impacts` | Energy or emission change per unit of each KPI |
| `project_targets.csv` | `nzc-ie/project_targets` | Sample project under action R3.1 (district heating phase 1) |
| `crosswalk_lacap_gpc.csv` | `nzc-ie/crosswalk_lacap_gpc` | Settings table: LACAP row → GPC sector and scope |
| `crosswalk_lacap_nzc.csv` | `nzc-ie/crosswalk_lacap_nzc` | Settings table: Irish rows passed into NZC sector "other" |
| `sources.csv` | — | Source registry for `--sources-csv` |

## What is from the plan and what is estimated

From the Dublin City Climate Action Plan 2024–2029 (printed page numbers):

- 2018 city total: **2,183,270 tCO2e** (p.67, Codema).
- Council's own emissions: 38,326 tCO2 in 2018 (p.67), 30,427 tCO2 in 2021 split by energy carrier (p.66).
- Population 592,713 in 2022 (p.5).
- Poolbeg waste-to-energy: 600,000 t waste a year, heat for 50,000–80,000 homes (p.25).
- Actions R1–R4 and RF1–RF4 with budgets (pp.38–42). The LED public lighting action (R3.4) avoids 2,500 tCO2e (p.40).

Estimated, because the plan's sector chart (Figure A3.3, p.67) and action tables are images that
could not be read here:

- **Sector split.** Commercial 32%, residential 27% and transport 25% come from web-search excerpts of
  the plan; the remaining 16% is split by Kausal using EPA national shares for a city.
- **Fuel split per sector.** Shares typical of an Irish city with gas grid coverage. Energy is
  back-calculated from emissions with the SEAI factors.
- **Grid emission factor after 2018.** National path to 0.10 t/MWh in 2030 and 0 in 2050.
- **Energy industries (Step 1).** Poolbeg waste-to-energy only (~0.4 t fossil CO2 per t waste). The
  gas-fired power stations are not included.
- **Action sizes.** For example, homes retrofitted, district heating connections and modal shift.
  These are scaled from national targets to Dublin City, or chosen to give a plausible path. The LED
  action is sized to match the plan's 2,500 tCO2e.
- **Simplifications.**
  - The model holds activity at the 2018 level in the baseline and changes it only through actions
    and the grid path.
  - Modal shift and electric cars both reduce car fuel and are added together. Their targets are kept
    at 95% of 2018 car-km or less, so car fuel never goes negative.
  - District heating heat is counted under waste/energy industries, not in Step 2.

**Replace these with Codema's Dublin City Baseline Emissions Inventory and the plan's Appendix 1 when
available:** change the `Value` (and `Source`/`Comment`) in the rows; the model does not change.

## Results with this data (computed 30 Oct 2026)

| | 2018 | 2030 | 2050 |
|---|---|---|---|
| Baseline (no new actions), kt CO2e | 2,183 | 1,636 (−25%) | 1,437 |
| Climate Action Plan scenario, kt CO2e | 2,183 | 1,413 (−35%) | 691 |
| Goal (−51% by 2030, neutral by 2050) | 2,183 | 1,070 | 0 |

GPC BASIC+ equals the LACAP total each year. GPC BASIC is lower by the industrial processes, F-gases,
agriculture and land rows (76 kt in 2018).

## Uploading

These are not yet in the dataset repository. Someone with DVC rights uploads each file, for example:

```bash
python tools/upload_new_dataset.py -i configs/data/nzc-ie/energy_inventory.csv -o nzc-ie --sources-csv configs/data/nzc-ie/sources.csv
```

Then set `dataset_repo.commit` in `configs/nzc-ie.yaml` and `configs/ie-lacap-dublin.yaml` to the new commit.
