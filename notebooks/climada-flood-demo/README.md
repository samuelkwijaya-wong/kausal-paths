# Flood adaptation demo: CLIMADA numbers for a Kausal Paths model

This folder holds a small, stand-alone script that uses
[CLIMADA](https://github.com/CLIMADA-project/climada_python) to work out expected
river-flood damage for a made-up city, "Riverford", with and without four
adaptation measures. Its results feed the Kausal Paths model in
`configs/riverford.yaml`.

It is a demonstration of how the two tools fit together, not a study of a real place.

## What is real and what is invented

| Part | Status |
|---|---|
| The city, its three districts and its building values | Invented |
| The river and the 1,000 flood events (today and in 2050) | Invented |
| The measures, their effects on floods or buildings, and their costs | Invented |
| Depth-damage curves | Real: JRC curves for Europe (Huizinga, de Moel and Szewczyk 2017, doi:10.2760/16510) |
| The damage calculation | CLIMADA 6.2.0 |

## How the two tools are connected

CLIMADA and Kausal Paths are kept apart. CLIMADA needs Python below 3.14 and
Kausal Paths needs 3.14 or newer, and CLIMADA's map-based calculation is too heavy
to repeat every time someone changes a setting in Paths. So:

1. `run_climada_flood.py` runs CLIMADA once and writes yearly tables.
2. Kausal Paths reads those tables and does the rest: switching measures on and
   off, discounting, and the cost-benefit charts.

Kausal Paths never imports CLIMADA.

## What the script does

1. Lays out a 30 x 30 grid of 100 m cells with a river along one edge and ground
   that rises away from it. Riverside and the Harbour are next to the river; the
   Old Town is on higher ground.
2. Draws 1,000 yearly peak river levels and turns them into flood depths. For
   2050 the peaks are 0.25 m higher and building values 20% higher.
3. Asks CLIMADA for expected annual damage per district in 2025 and 2050: with no
   measures, with each measure alone, and with all four together.
4. Draws a straight line between 2025 and 2050 to get a value for every year.
   A measure has no effect until the year after its construction ends.
5. Checks its own results (see below) and writes the output files.

The measures are defined in `measures.yaml`, which can be edited:

| Measure | What it does in CLIMADA | Cost |
|---|---|---|
| Raise the river dike | No damage from floods more frequent than 1 in 50 years, in Riverside and the Harbour | EUR 40 M over 2027-2029, then 0.4 M a year |
| Flood-proof properties | Damage cut by a quarter in Riverside and the Old Town | EUR 15 M over 2026-2030, then 0.1 M a year |
| Restore the upstream floodplain | Flood depths 0.3 m lower everywhere | EUR 25 M over 2026-2028, then 0.2 M a year |
| Relocate the lowest riverside strip | Homes in the two lowest rows of Riverside moved to high ground | EUR 60 M over 2028-2032 |

## Limits to keep in mind

- **Combining measures is approximate.** CLIMADA scores each measure on its own.
  Kausal Paths combines them by multiplying the shares of damage each one leaves
  behind. Measures that tackle the same floods overlap, so this overstates the
  joint benefit. For all four measures in 2050, CLIMADA's own combined run leaves
  14.6 million EUR a year of damage and the Paths rule leaves 10.2 million; in
  terms of damage avoided that is 41.7 against 46.1 million (11% too high).
  `output/combined_check.csv` has the comparison for every year.
- **Only two years are calculated.** Values between 2025 and 2050 are a straight
  line, not separate simulations. The years 2020-2025 are shown flat at the 2025
  level.
- **Measures are stylised.** Each is a simple change to flood depth, flood
  frequency, damage share or building location.
- **No map.** Kausal Paths shows results by district in charts, not on a map.

## Running it

CLIMADA needs its own Python environment (3.11 to 3.13). The script was run with
Python 3.12 on Ubuntu 24.04 using the system GDAL library:

```bash
sudo apt-get install libgdal-dev g++ python3.12-dev
```

```bash
uv venv --python 3.12 climada-venv
```

```bash
uv pip install --python climada-venv/bin/python -r requirements.txt "gdal==$(gdal-config --version)"
```

```bash
climada-venv/bin/python run_climada_flood.py
```

CLIMADA's own documentation recommends installing with conda or mamba
(`mamba install -c conda-forge climada`) instead; that route was not tried here.

The script takes about a minute. Running it again with the same `--seed` gives
identical files.

## Output

In `output/`:

- `climada_endpoints.csv`: CLIMADA's results for 2025 and 2050, per district and case.
- `flood_damage_baseline.csv`: yearly expected damage without measures.
- `measure_effects.csv`: yearly damage with each measure alone, and the share avoided.
- `measure_costs.csv`: yearly investment and maintenance per measure.
- `combined_check.csv`: all measures together, CLIMADA against the Paths rule.
- `benefit_cost_report.csv`: discounted avoided damage and cost per measure.
- `paths_upload_wide.csv`: the same numbers in one table, for a later upload as a regular Kausal dataset.
- `run_metadata.json`: CLIMADA version and seed.

The script also rewrites `configs/modules/riverford/climada_results.yaml`, the
data file the Paths model includes. That file stores the numbers inline, which
Kausal Paths treats as a first-draft approach; the proper home for them is a
dataset in the Kausal dataset repository.

## Checking the Paths model

```bash
python load_nodes.py -c configs/riverford.yaml --validate
```

```bash
python load_nodes.py -c configs/riverford.yaml --scenario baseline --node flood_damage
```

The baseline figures should equal `flood_damage_baseline.csv`, and each measure's
discounted avoided damage and cost in the cost-benefit overview should equal
`benefit_cost_report.csv` (at a 3% discount rate).

## Using real data

CLIMADA can download ready-made flood and asset data for real countries through
its Data API (`climada.ethz.ch`). That was not used here: the demo was built
where that server could not be reached, and its data is coarse (about 4 km) for a
single city. A real city model would need local flood maps and building data.

## Licence

CLIMADA is free software under the GNU GPL version 3. This script uses it as a
separate program. The JRC damage-curve values are reproduced from
`climada_petals` 6.2.0 with the citation above.
