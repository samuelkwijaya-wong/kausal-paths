# BCDCOG demo model: data

`bcdcog_datasets.csv` holds every number the demo model `configs/bcdcog.yaml` uses, in the wide upload format
(`docs/dataset-csv-format.md`). Each row says in `Source` which page, figure or table of the Regional Climate
Action Plan (September 2026) it comes from. `Comment` says where a value was read off a chart, calibrated or
assumed.

| Dataset id | What it holds |
|---|---|
| `bcdcog/emissions_inventory` | 2023 emissions by sector and energy source (Figure 3.1), 14.6 Mt in total |
| `bcdcog/sequestration` | −1.8 Mt absorbed by natural and working lands, held flat |
| `bcdcog/bau_growth_index` | Business-as-usual growth per sector, 2023 = 1 (pp. 36–37) |
| `bcdcog/action_factors_by_fuel` | Share of emissions remaining under the grid, vehicle-standard and EV actions |
| `bcdcog/action_factors_by_sector` | Share remaining under building retrofits |
| `bcdcog/rapid_transit` | Trips replaced by Lowcountry Rapid Transit, trip length and car emission factor |
| `bcdcog/bus_electrification` | Diesel saved by an electric CARTA fleet (assumed) |
| `bcdcog/population` | Population, 2023 and 2050 |

## Setting up the instance

The model reads its data from the shared DVC repository, so the CSV has to be uploaded once. This needs DVC
write credentials (`DVC_PANDAS_GIT_TOKEN` etc.).

```bash
# 1. Upload. Prints the new dataset-repo commit.
python -m tools.upload_new_dataset -i data/bcdcog/bcdcog_datasets.csv -o bcdcog --instance bcdcog --language en

# 2. Put that commit into `dataset_repo.commit` in configs/bcdcog.yaml.
#    `--pull-datasets` advances it to the repo's latest commit instead.

# 3. Check that it computes.
python load_nodes.py -c configs/bcdcog.yaml --node net_emissions

# 4. Create the instance in the database, with its pages.
python load_nodes.py -c configs/bcdcog.yaml --update-instance --update-nodes
```

To change a number, edit the CSV and repeat steps 1–2.
