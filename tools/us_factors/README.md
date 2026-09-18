# US emission factors

A library of US emission factors built from public federal sources, so that US
city models share one set of factors instead of each carrying its own copy.

## Why

Paths has a shared factor library for exactly one country. Germany's is the `de/`
dataset namespace, declared once in `configs/modules/bisko/model.yaml` and pulled
in by seven city configs through a single `include:`.

US cities have no equivalent, so each transcribes the same public EPA numbers by
hand:

| City | Its own copy |
|---|---|
| Sedona | `sedona/grid_emission_factors`, `sedona/stationary_emission_factors`, `sedona/vehicle_emission_factors`, `sedona/waste_emission_factors` |
| Longmont | `longmont/electricity_emission_factor`, `longmont/emission_factor_natural_gas`, `longmont/emission_factor_fuels` |
| Minneapolis | `electricity_emission_factors`, `fossil_gas_emission_factors`, `onroad_fuel_emission_factors`, `onroad_mileage_emission_factors` |

Same numbers, six places, no record of which eGRID release each came from.

## What it produces

One CSV per dataset in `tables/`, in the upload format of
[`docs/dataset-csv-format.md`](../../docs/dataset-csv-format.md):

| Dataset | Source | Dimensions | Unit |
|---|---|---|---|
| `egrid_grid_factors` | EPA eGRID | `egrid_subregion`, `greenhouse_gas` | `lb/MWh` |
| `epa_stationary_factors` | EPA Emission Factors Hub | `fuel`, `greenhouse_gas` | `kg/MMBtu` |
| `epa_mobile_mileage_factors` | EPA Emission Factors Hub | `vehicle_type`, `greenhouse_gas` | `g/mile` |
| `grid_factor_projection` | NREL Cambium | `cambium_region`, `scenario` | `kg/MWh` |

A city picks its own region out of the shared table with a `filters:` entry on
the dataset binding, driven by one instance parameter — the same mechanism
`configs/bisko.yaml` already uses to filter shared `de/` tables down to one
municipality.

## Running it

Needs network access to epa.gov. Some environments (including Claude Code's
cloud sandbox) block it; see *Offline* below.

```bash
python -m tools.us_factors.build_csv --all          # every source, default releases
python -m tools.us_factors.build_csv --egrid 2023   # one eGRID release
```

Downloads land in `cache/` (gitignored) with a `.provenance.json` beside each
recording the URL, retrieval time and SHA-256 of what arrived. Re-runs reuse the
cache; `--refresh` re-downloads.

### Publishing onwards

The generated CSVs enter the model through the existing route:

```bash
python -m tools.upload_new_dataset -i tools/us_factors/tables/egrid_grid_factors.csv \
    -o us -l en -n <instance>
# then bump the dataset_repo commit in the instance YAML, and:
python manage.py load_dvc_dataset <instance> us/egrid_grid_factors --plan
```

### Offline

`--offline` never touches the network. If a source is missing it fails with the
URL to fetch and the exact path to put it at:

```
egrid2023 is not cached and offline mode forbids downloading it.
  Expected file: tools/us_factors/cache/egrid2023.xlsx
  Download from: https://www.epa.gov/system/files/documents/2025-01/egrid2023_data.xlsx
```

Download it elsewhere, drop it at that path, and re-run. A hand-placed file needs
no accompanying metadata — the build records its checksum and edition on adoption.

NREL Cambium is always manual — its Scenario Viewer requires accepting terms
before download, so there is no URL a script can GET. `build_csv.py` prints the
instructions when the file is absent.

### When a publisher changes a layout

EPA re-lays-out its workbooks between editions. The parsers locate data by header
*text* rather than cell position, so most changes pass through — but when one
doesn't, the error names the sheet, the header row and the columns it did find.
To see the file's actual structure:

```bash
python -m tools.us_factors.build_csv --inspect egrid2023
```

For the Hub, each table is a declaration (`HubTable` in `sources/epa_hub.py`)
rather than bespoke code, so adapting is usually editing a tuple of header
tokens.

## Checking the library against the existing models

Two reports, because the question splits in two.

### What the cities carry today (no data needed)

```bash
python -m tools.us_factors.survey
```

Reads `configs/` and lists every emission-factor node in the US instances, its
unit, its dimensions and the dataset behind it. It needs no network, no database
and no exports, and it is the fastest way to see the problem: today it reports
**83 factor nodes across 7 instances, 6 dataset namespaces and nothing shared
between cities**, with the same physical quantity written `lb*CO2e/MWh`,
`lbs/MWh` and `t_co2e/MWh`, and the greenhouse-gas dimension called `ghg`,
`greenhouse_gas` and `greenhouse_gases` in different models.

### Whether the numbers agree (needs the library built and the cities exported)

```bash
python manage.py export_dataset sedona sedona/grid_emission_factors \
    --out /tmp/city-exports --format wide
python -m tools.us_factors.compare_to_cities --city-dir /tmp/city-exports
```

Reports four outcomes per factor and year, not two: **agrees**, **differs**,
**incomparable units**, and **present on only one side**. The last two are where
most of the findings are, so they are reported rather than folded into the
others, and mappings that matched nothing are listed separately — a mapping that
compared nothing is not evidence of agreement.

Each city↔library correspondence is declared explicitly in `city_factors.py`,
because it is a human claim rather than something the data says. Two kinds of
uncertainty are marked there and must be resolved before trusting a result: the
eGRID subregion (only Sedona's is documented in its own config) and the exact
dimension category ids.

Where a city series is not reduced to one line — Sedona's grid factor varies by
`electricity_user`, and its wastewater plant is charged zero in 2023–24 — the
comparison **refuses and names the dimension** rather than picking a row.

## Tests

```bash
python -m pytest tools/us_factors/tests/
```

The fixtures are synthetic workbooks with **invented round-number values**. They
test that the parser finds the right cell and labels it correctly — the mapping
from a spreadsheet's shape to a tidy row. They deliberately do not assert real
EPA figures: a half-remembered factor baked into a test gives false confidence
exactly where this package must not have any.

## The rule this package is built around

**No factor is ever emitted that was not read out of a published file.** There is
no default, no fallback, no built-in table. A wrong-but-plausible emission factor
does not error — it computes, and quietly makes a city's answer wrong. So every
failure path here raises rather than substitutes.

## Status

Phases 1 and 2: sources, parsers, provenance, the config survey and the
comparison (107 tests passing).

`tables/` is empty until the build is run somewhere that can reach epa.gov — the
code was written in an environment whose egress policy blocks it, which is
precisely why nothing here falls back to a built-in value.

Not yet built:
- The shared config fragment `configs/modules/us/emission_factors.yaml` and the
  factor nodes that read these tables, following the national/local port pattern
  of `configs/modules/bisko/model.yaml`.
- EPA Hub mobile CO2 (per gallon) and waste factors. Each is one more `HubTable`
  declaration plus a test, once its layout has been checked against the real
  workbook.
- Mappings in `city_factors.py` for King County and Hollywood.
