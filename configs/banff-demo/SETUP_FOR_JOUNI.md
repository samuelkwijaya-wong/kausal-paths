# Banff demo - setup note

Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap.
Not prepared or endorsed by the Town of Banff.

Instance `banff-demo`, "Banff (illustrative demo)". YAML-sourced. Private: shared with CEA
(Community Energy Association) only.

## Files

| File | What |
|---|---|
| `configs/banff-demo.yaml` | The instance config |
| `configs/banff-demo/banff_demo_data.csv` | 15 datasets, wide format, for `tools/upload_new_dataset` |
| `configs/banff-demo/banff_demo_template_2026.csv` | 1 template dataset with deliberately blank 2026 cells |
| `configs/banff-demo/banff_demo_sources.csv` | Sources registry (3 entries, each carrying the demo notice) |
| `configs/banff-demo/make_banff_demo_data.py` | Producer: writes the three CSVs from the Roadmap figures and checks the totals |
| `configs/banff-demo/check_banff_demo.py` | Runs the model from the CSVs without DVC and checks it against the Roadmap |
| `configs/banff-demo/RECONCILIATION.md` | Output of the check: all checks pass |
| `configs/banff-demo/DATA_NOTES.md` | Assumptions, simplifications, and the Roadmap's own inconsistencies |

Nothing in the platform code or the UI was changed.

## Steps

1. Optional: re-run the check locally (no DVC needed).

   ```bash
   PYTHONPATH=. python configs/banff-demo/check_banff_demo.py
   ```

2. Upload the datasets to dvctest under `banff-demo/`. The instance loads from YAML without its
   datasets, so `-n banff-demo` works before the upload.

   ```bash
   python -m tools.upload_new_dataset -i configs/banff-demo/banff_demo_data.csv -o banff-demo -l en -n banff-demo --sources-csv configs/banff-demo/banff_demo_sources.csv
   ```

   ```bash
   python -m tools.upload_new_dataset -i configs/banff-demo/banff_demo_template_2026.csv -o banff-demo -l en -n banff-demo --sources-csv configs/banff-demo/banff_demo_sources.csv --keep-empty-cells
   ```

   The dataset ids this produces are `banff-demo/emissions_inventory`,
   `emissions_business_as_usual`, `emissions_roadmap_published`, `inventory_reconciliation`,
   `emissions_by_fuel_source`, `energy_use_by_sector`, `energy_use_by_fuel`, `residents`,
   `visitors`, `visitor_presence`, `floor_area`, `waste_tonnage`, `grid_emission_factor`,
   `global_warming_potential`, `roadmap_action_effects` and `reconciliation_indicators`.
   I ran the upload pipeline up to the push (`build_dvc_frame` and `build_sources_metadata`)
   for all 16 without errors; the push itself was not run.

3. Set `dataset_repo.commit` in `configs/banff-demo.yaml` to the dvctest commit that holds them.
   It currently carries a placeholder commit and a comment saying so.

4. Create the instance from the YAML and its node rows.

   ```bash
   python load_nodes.py -c configs/banff-demo.yaml --update-instance --update-nodes
   ```

5. Load the datasets into the database so they can be edited in the admin (the config has
   `use_datasets_from_db: true`; without database rows the model reads DVC directly, so this
   step can wait if editing is not needed for the demo).

   ```bash
   python manage.py dataset_status banff-demo
   ```

   then run the `load_dvc_dataset banff-demo <ids> --force` line it prints.
   `reconciliation_indicators` is not read by any node; load it by name if the 2026 template
   should be visible in the admin.

6. Hostname, theme (`default` for now) and user access for CEA. The config sets
   `requires_authentication: true`.

## Decisions for you

- **Hosting and access**: which server and hostname, and how CEA users get accounts.
- **Admin editing**: whether to load the datasets into the database now (step 5).
- **Theme**: `default`. A Kausal demo theme may suit better; it must not look like the Town's.
- **Where the files live**: they are in `configs/banff-demo/` on this branch because `data/` is
  git-ignored. If a paths-data `models/banff-demo/` folder is the better home for the producer
  and CSVs, they can move there.

## Things that behave unusually

- The "baseline" scenario is "No change from 2016", a flat reference line. Business as usual is
  its own scenario (`business_as_usual`), made of the three "happens regardless" actions, so
  that the RFP's three-way split shows on the action list.
- The three "happens regardless" actions are `linear.DatasetReduceAction`s from the 2016
  inventory to the published BAU 2050 values.
- Years between published points are written into the CSVs as straight lines. Left to
  `LinearInterpolation`, the interpolated years after 2016 were flagged as historical
  (`interpolate_years` forward-fills the Forecast flag from the left-hand point). That may be
  worth a look in the platform, separately from this demo.
- `roadmap_published_emissions` uses `from_year(..., 2050)` so it shows only its one year.
- `inventory_reconciliation_emissions` holds its 2026 value flat after 2026; only 2016 and 2026
  are meant to be read.
