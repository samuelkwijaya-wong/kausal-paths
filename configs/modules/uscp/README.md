# Kausal Paths model template for US communities (USCP-structured inventory)

## Status in one paragraph

This directory holds the template: an inventory layer structured by the ICLEI U.S. Community Protocol (USCP) v1.2, a business-as-usual (BAU) forecast and a library of 24 climate actions, wired so that overlapping actions cannot remove more than the activity they act on. The category structure has been checked against the USCP v1.2 text. The template itself still carries **no default values**: every default needs a citation and none has been sourced yet. A **demo instance for the City of Vancouver, Washington** (`configs/vancouver-wa-uscp.yaml`) loads the City's 2023 and adjusted 2019 inventories and reproduces both published totals; its **action effects are illustrative placeholders** for sales demonstration. See [Status against the acceptance checks](#status-against-the-acceptance-checks) and [Open questions](#open-questions).

## What the model does

A city loads its own community-wide greenhouse gas inventory, structured by the USCP. The model:

1. reproduces that inventory in each inventory year, category by category;
2. carries it forward as a BAU forecast using population, jobs, VMT per resident and the grid emission factor trajectory;
3. lets the city switch on actions from its plan, each changing a specific activity or emission factor;
4. reports every result in the inventory's own USCP categories and, through a second tag, in GPC-style sectors (Stationary Energy, Transportation, Waste, IPPU, AFOLU).

Because actions act on the inventory's own categories, the forecast, the inventory and progress reporting use the same structure, with no mapping into a separate set of planning categories.

The model uses a USCP-structured inventory as its input. It does not check, produce or certify an inventory against the protocol.

## Files

| File | Contents |
|---|---|
| `inventory.yaml` | Dimensions `uscp_category` and `gpc_sector`; inventory input nodes; activity x emission factor calculations; BAU projection; reporting nodes |
| `drivers.yaml` | BAU drivers: population, jobs, VMT per resident, grid emission factor, conversion factors |
| `actions.yaml` | Action library (24 actions), each with a zero-effect series until parameterised |
| `sources.csv` | Source register: every document used or intended, its status and what it supplied |
| `README.md` | This file |
| `../../vancouver-wa-uscp.yaml` | Demo instance: City of Vancouver, WA |

## Inventory categories

Every emissions node carries two tags, as dimensions on `net_emissions`. Category names follow the sectors of USCP v1.2 (Appendix B summary table, pp.72-75; Table 2, pp.17-18), split further where actions need it. The five basic emissions-generating activities are those of Section 2.2 (pp.26-28).

| USCP category (`uscp_category`) | GPC sector (`gpc_sector`) | USCP basic activity | How it is modelled | Instance inputs |
|---|---|---|---|---|
| Built Environment: residential energy | Stationary energy | Electricity use; fuel combustion | Activity x emission factor, by fuel | Electricity (MWh), natural gas (therms), other fuels (MMBtu) |
| Built Environment: commercial energy | Stationary energy | Electricity use; fuel combustion | Activity x emission factor, by fuel | As residential |
| Built Environment: industrial energy | Stationary energy | Electricity use | Activity x emission factor, by fuel | As residential |
| Transportation: on-road passenger, freight and transit vehicles | Transportation | On-road travel | VMT x emission factor: light-duty, medium/heavy-duty and transit | Total VMT, light-duty share, transit VMT, three emission factors |
| Transportation: other mobile sources | Transportation | No | Inventory total | Emissions (t CO2e) |
| Solid Waste | Waste | Solid waste generation | Tonnes x emission factor, organics and other materials | Tonnes landfilled, organics share, three emission factors |
| Water and Wastewater: energy use | Stationary energy | Water and wastewater energy | Activity x emission factor | Electricity, natural gas |
| Water and Wastewater: process emissions | Waste | No | Inventory total, scaled by population | Emissions (t CO2e) |
| Agriculture | AFOLU | No | Inventory total | Emissions (t CO2e) |
| Process and fugitive emissions | IPPU (process); Stationary energy (fugitive) | No | Inventory totals | Two emission totals |
| Forests and Lands | AFOLU | No | Forest: inventory net flux. Trees outside forest: canopy area x removal factor | Net flux, canopy area, removal factor |
| Upstream Impacts of Community-Wide Activities | Stationary energy | No | Transmission and distribution losses as a share of electricity emissions (Appendix C method BE.4.1) | Loss share |

Notes from the protocol:

- **On-road VMT** is used as the inventory published it. USCP v1.2 Appendix D has two methods whose results "should not be compared": TR.1.A, the recommended origin-destination method (p.12), and TR.1.B, the alternative in-boundary method (p.18). Record which one the inventory used. (The earlier project crosswalk brief had these two codes the other way round.)
- **Transit** is kept apart from other on-road travel, as in Appendix D method TR.4 (p.39).
- **Forests and Lands:** Section 1.1 (p.13) recommends reporting land-use fluxes as a separate category alongside gross emissions in the other sectors. The node `gross_emissions_excluding_land` gives that gross total.
- **Composting:** Appendix E provides no composting emission factor (method SW.3, p.21).
- Electricity used to charge vehicles that actions electrify is reported under on-road transport (GPC Transportation). Charging that already existed in the inventory years stays inside the building electricity figures.

## How a city's inventory is loaded

A city gets its own instance file in `configs/` (see `configs/vancouver-wa-uscp.yaml`), which includes the three modules and replaces each input node with its own figures. Including with `allow_override: true` means a node the instance defines replaces the template node with the same id completely, so the instance repeats `type`, `quantity` and `unit`.

```yaml
id: example-city
reference_year: 2019            # the earliest inventory year
minimum_historical_year: 2019
maximum_historical_year: 2023   # the latest inventory year
emission_unit: t/a
emission_dimensions: [uscp_category, gpc_sector]

include:
- file: modules/uscp/inventory.yaml
  allow_override: true
- file: modules/uscp/drivers.yaml
  allow_override: true
- file: modules/uscp/actions.yaml
  allow_override: true

# include does not merge these, so the instance defines them
action_groups:
- {id: electricity, name: Electricity}
- {id: buildings, name: Buildings}
- {id: transportation, name: Transportation}
- {id: waste, name: Waste}
- {id: water, name: Water and wastewater}
- {id: land_use, name: Land use}

emission_sectors:
- id: net_emissions
  name: Net emissions
  is_outcome: true

nodes:
- id: residential_electricity_use_inventory
  name: Residential electricity use (inventory)
  description: 'Source: <document>, <publisher>, <year>, <table or page>, <URL>.'
  type: simple.AdditiveNode
  quantity: energy
  unit: MWh/a
  historical_values: [[2019, <value>], [2023, <value>]]
```

Rules for inputs:

- Every node whose description starts with "Instance input" needs a value and a citation in the node description, plus a row in the instance's source register.
- Every input needs a value for **every inventory year**, otherwise that year drops out of the results.
- Drivers (`population`, `jobs`, `vmt_per_capita`, `grid_electricity_emission_factor`) need historical values that cover all inventory years and **end in the latest inventory year**, and forecast values that **start in the year after it**. The forecast flag of years between data points is copied forward from the previous point, so a forecast that starts later would be read as history.
- Where the inventory reports only a sector total, use the total nodes. Where it reports activity data and emission factors, enter both so actions can act on the activity.
- In each inventory year, activity x emission factor must reproduce the published category totals. Record the tolerance and any difference in the instance header.

The input nodes map one to one onto fields for a future data-entry interface in Kausal Paths; nothing in this template depends on that interface.

## Business-as-usual forecast

Each inventory activity is multiplied by its driver relative to the latest inventory year (edge tags `ratio_to_last_historical_value` and `indifferent_history_ratio`), so every inventory year is reproduced exactly and growth applies only to forecast years:

- residential energy, on-road VMT, transit, solid waste, water and wastewater: population;
- commercial and industrial energy: jobs;
- on-road VMT also: VMT per resident;
- electricity: the grid emission factor trajectory entered by the city;
- vehicles: the fleet emission factor forecasts entered by the city (held at the last value if none are entered).

Other transport, livestock, process, fugitive and forest totals are held at the latest inventory value.

## Action library

All actions are `simple.AdditiveAction` nodes. Each one's key parameter is a time series by year, which carries the adoption rate, the start year and the target year in one place. **No template default has a citation yet, so every default, range and citation below is empty.** Each action ships with a zero-effect series meaning "not parameterised" (open question Q7). The Vancouver demo overrides all of them with illustrative placeholder trajectories.

| Action | Inventory category (GPC sector) | Causal path | Parameter (unit) | Default | Range | Citation |
|---|---|---|---|---|---|---|
| Clean electricity procurement | All electricity categories; on-road charging; losses (Stationary energy; Transportation) | Lowers the electricity emission factor | Extra zero-carbon share of community electricity (%) | none | none | none |
| Residential rooftop and community solar | Residential energy (Stationary energy) | Subtracts from residential electricity | Additional generation (MWh/a) | none | none | none |
| Commercial rooftop and community solar | Commercial energy (Stationary energy) | Subtracts from commercial electricity | Additional generation (MWh/a) | none | none | none |
| Residential efficiency retrofits | Residential energy | Lowers residential electricity, gas and other fuels | Reduction in residential energy use (%) | none | none | none |
| Commercial efficiency retrofits | Commercial energy | Lowers commercial electricity, gas and other fuels | Reduction in commercial energy use (%) | none | none | none |
| Building performance standard | Commercial energy | As retrofits, applied after them | Reduction in commercial energy use (%) | none | none | none |
| Residential electrification | Residential energy | Moves remaining gas to electricity | Share of remaining gas displaced (%) | none | none | none |
| Commercial electrification | Commercial energy | As residential | Share of remaining gas displaced (%) | none | none | none |
| All-electric new homes | Residential energy | Moves gas to electricity | Share of residential gas avoided (%) | none | none | none |
| All-electric new commercial buildings | Commercial energy | Moves gas to electricity | Share of commercial gas avoided (%) | none | none | none |
| Active transport mode shift | On-road (Transportation) | Lowers light-duty VMT | Reduction in light-duty VMT (%) | none | none | none |
| Transit service expansion | On-road | Lowers light-duty VMT | Reduction in light-duty VMT (%) | none | none | none |
| VMT reduction through land use | On-road | Lowers light-duty VMT | Reduction in light-duty VMT (%) | none | none | none |
| Light-duty EV adoption | On-road | Moves light-duty VMT to electric | Share of remaining light-duty VMT electrified beyond BAU (%) | none | none | none |
| Public EV charging buildout | On-road | As EV adoption, further share | Additional share electrified (%) | none | none | none |
| Municipal fleet electrification | On-road | As EV adoption, further share | Fleet share of light-duty VMT x share electrified (%) | none | none | none |
| Medium and heavy-duty ZEVs | On-road | Moves medium/heavy-duty VMT to electric | Share electrified beyond BAU (%) | none | none | none |
| Transit bus fleet electrification | On-road | Moves transit vehicle miles to zero-emission buses | Share of transit vehicle miles electrified (%) | none | none | none |
| Organics diversion and composting | Solid Waste (Waste) | Moves landfilled organics to composting | Share of landfilled organics diverted (%) | none | none | none |
| Landfill gas capture improvement | Solid Waste | Lowers landfill emissions | Reduction in landfill emissions (%) | none | none | none |
| Recycling rate increase | Solid Waste | Lowers landfilled other materials | Share diverted (%) | none | none | none |
| Water and wastewater treatment energy efficiency | Water and Wastewater: energy (Stationary energy) | Lowers utility electricity and gas | Reduction in utility energy (%) | none | none | none |
| Wastewater process emissions reduction | Water and Wastewater: process (Waste) | Lowers process emissions | Reduction in process emissions (%) | none | none | none |
| Urban tree canopy expansion | Forests and Lands (AFOLU) | Adds canopy area that removes carbon | Canopy added since the latest inventory year (ha) | none | none | none |

Cost per action (USD) is a key parameter in the brief but is not wired yet (open question Q8).

### How to parameterise an action

Override it in the instance with the city's trajectory and cite every number in its description. Keep zeros up to the latest inventory year, start the forecast in the next year, and **write every value as a decimal** (`0.0`, `20.0`): Kausal Paths refuses to join a whole-number history with a decimal forecast.

```yaml
actions:
- id: light_duty_ev_adoption
  name: Light-duty electric vehicle adoption
  description: 'Source: <CAP or CCAP>, <publisher>, <year>, <measure table, page>, <URL>.'
  type: simple.AdditiveAction
  group: transportation
  quantity: fraction
  unit: '%'
  historical_values: [[1990, 0], [2023, 0]]
  forecast_values: [[2024, 0], [2030, <value>], [2045, <value>]]
  input_dataset_processors: [LinearInterpolation]
```

### How to add an action

1. Decide which activity or emission factor the action changes. If none fits, add the activity to `inventory.yaml` first; an action should never create emissions outside the inventory categories.
2. Express its effect as either a share of that activity (unit `%`) or an absolute amount in the activity's unit.
3. A share enters the activity's `MultiplicativeNode` as an input with `tags: [complement]`, listed after the activity itself (the first input sets the years). An absolute amount enters as an added input with `tags: [forecast_only, truncate_beyond_end]`: adding takes the union of years and fills gaps with zero, so without these tags the action's series would write zeros into years without inventory data.
4. Decide its order relative to other actions on the same activity and document the overlap (next section).
5. Ship it with `historical_values: [[1990, 0], [2100, 0]]` until a cited default exists, add its parameter to the table above and its sources to `sources.csv`.

## Double counting

The rule: **actions acting on the same activity are combined as sequential factors, never as added reductions.** For shares a, b and c applied to the same activity, the result is activity x (1 - a) x (1 - b) x (1 - c). Each action acts on what the previous ones left, so together they can never remove more than the activity, provided each share stays between 0 and 100%. Kausal Paths does not clamp shares, so the instance must keep them in that range. Results of subtractions (electricity after solar, displaced gas, electric VMT) are only ever subtractions of a smaller quantity from a larger one, and electricity after solar is additionally clipped at zero.

| Overlap | Handling |
|---|---|
| Mode shift, transit expansion and land use all reduce car travel | Sequential factors on light-duty VMT |
| Demand reduction and EV adoption both reduce gasoline use | EV adoption applies only to the VMT left after demand actions (shared driver: light-duty VMT) |
| EV adoption, public charging and municipal fleet electrification | Sequential factors on the combustion share; each parameter is the share of what remains. If the city's EV figure already assumes the charging buildout, charging stays at zero |
| EV adoption and state vehicle rules in the BAU | The BAU fleet emission factor carries state rules; the EV parameter counts only adoption beyond BAU |
| Retrofits and building performance standard | Sequential factors on commercial energy, retrofits first |
| Efficiency and electrification | Electrification acts on the gas left after efficiency; the displaced gas becomes electricity through one conversion factor |
| Electrification of existing buildings and all-electric new construction | Sequential factors on the remaining gas |
| Electrification and EV charging add electricity; clean procurement lowers its emission factor | Added electricity is counted at the procurement-adjusted factor, so procurement is applied once to all community electricity |
| Local solar and clean procurement | Solar lowers the electricity bought; procurement applies to the rest |
| Grid BAU trajectory and clean procurement | The grid trajectory must exclude the city's own procurement |
| Transmission losses and every electricity action | Losses are a share of electricity emissions, so they fall with them and are never reduced separately |
| Organics diversion and landfill gas capture | Capture applies to the organics still landfilled |
| Organics diversion and recycling | Act on separate fractions (organics, other materials), each a share of its own fraction |

## Reporting

- **USCP categories:** `net_emissions` by `uscp_category`.
- **GPC sectors:** the same results by `gpc_sector`.
- **Gross emissions:** node `gross_emissions_excluding_land`, the total without Forests and Lands (USCP v1.2 Section 1.1, p.13).
- **USCP basic activities:** node `uscp_basic_activities_emissions`, the sum of the five basic emissions-generating activities (Section 2.2, pp.26-28). It is a sum of model results, not a statement that the inventory meets the protocol.

## Demo instance: City of Vancouver, Washington

`configs/vancouver-wa-uscp.yaml`. Chosen by Samuel Wijaya as the sales demo.

- **Inventory:** City of Vancouver 2023 Inventory of Community and Government Operations Greenhouse Gas Emissions (September 2024), which follows USCP v1.2 and was calculated in ClearPath. Both the 2023 inventory (Table 1) and the City's adjusted 2019 inventory (Table 11) are loaded.
- **Reconciliation:** the model reproduces the published totals: 2023, 1,456,611 t CO2e (difference 0); 2019, 1,763,769 against 1,763,768 (rounding). Differences by category come only from using one natural gas factor for all sectors (each under 0.15%).
- **Drivers:** population and jobs from the City's Comprehensive Plan materials (economic analysis, June 2024; adoption release, June 2026); grid factor falling to zero in 2045 under Washington's Clean Energy Transformation Act, on an assumed straight line.
- **Illustrative, not cited:** all 24 action trajectories, plus five technical factors: electricity per therm displaced, EV electricity per mile (light-duty and medium/heavy-duty), organics share of landfilled waste and the urban tree removal factor (taken from a hypothetical example in USCP Appendix J). Each is marked ILLUSTRATIVE or ILLUSTRATIVE PLACEHOLDER in its description.
- **Assumptions (marked ASSUMPTION):** VMT per resident and fleet emission factors held at 2023 values; the base year of the City's 2045 growth figures taken as 2023.
- **Licence:** the inventory report is published under CC BY-NC-ND 4.0. The instance uses only its numeric figures, with attribution (open question Q14).
- **Results (engine run):**

  | Year | Business as usual (t CO2e) | Illustrative action scenario (t CO2e) |
  |---|---|---|
  | 2019 | 1,763,767 (inventory) | 1,763,767 |
  | 2023 | 1,456,611 (inventory) | 1,456,611 |
  | 2030 | 1,492,643 | 1,269,475 |
  | 2040 | 1,499,247 | 818,371 |
  | 2045 | 1,482,756 | 805,541 |

  In BAU, population growth (+40% by 2045) outweighs grid decarbonisation. In 2040 the action scenario still leaves aviation and off-road (182 kt), refrigerants (138 kt), industrial energy (116 kt) and on-road transport (263 kt), none of which the starter action library fully addresses, against the City's carbon-neutral goal for 2040.

## Limitations

- The template has no cited default values; the demo's actions are placeholders.
- One efficiency share per action applies to all fuels in a sector; electrification applies to natural gas only, not propane or fuel oil.
- One natural gas emission factor for all sectors.
- Transit service expansion does not add the emissions of the extra service.
- Electric buses use the medium/heavy-duty electricity-per-mile factor.
- Other transport, livestock, process, fugitive and forest emissions are held at the latest inventory value with no actions.
- One removal factor for all urban canopy, regardless of tree age.
- Harvested wood products and consumption-based emissions are not included.
- Upstream benefits of recycling are outside the inventory and not counted.
- No GPC scope tagging, and no tagging of in-boundary sources versus community activities (open question Q4).

## Status against the acceptance checks

| Check | Status |
|---|---|
| Demo instance runs without errors | **Met, with a caveat.** It computes without errors in the Kausal Paths engine (both scenarios, all nodes feeding `net_emissions`), against a local PostgreSQL/PostGIS database. The build environment cannot download Python 3.14, so the run used Python 3.13 with a local compatibility shim (postponed annotations, PEP 758 syntax, an `annotationlib` stand-in). Re-run on Python 3.14 before the demo: `python load_nodes.py -c configs/vancouver-wa-uscp.yaml --node net_emissions` |
| Baseline totals match the published inventory | **Met** in the engine run: 2023 1,456,611 t (published 1,456,611); 2019 1,763,767 t (published 1,763,768). By category the differences are -64 t (residential), -54 t (commercial) and +118 t (industrial), from the single natural gas factor |
| Every default has a citation; no uncited numbers | **Met for the template** (no defaults). **Not met for the demo, by design:** action trajectories and five technical factors are illustrative placeholders, each labelled |
| Nothing copied from the Transition Element Framework | Met. The TEF repository was not opened |
| Actions show effects in the inventory categories and by GPC sector | Met: computed results by `uscp_category` and by `gpc_sector` in both scenarios |
| Overlapping actions cannot exceed the underlying activity | Met in structure (sequential factors), as long as each share stays within 0 to 100% |

The static validator merges the include files as the Kausal Paths loader does and checks node references, dimensions and categories, edge tags, and units, including which inputs of each multiplicative node are multiplied and which are added. It was tested by introducing deliberate errors, which it caught.

## Open questions

Questions marked "brief" were raised in the project brief; the rest came up during the build. The numbers are referenced from the YAML files.

- **Q1 (resolved).** Category list and basic activities checked against USCP v1.2 (Section 2.2, Table 2, Appendix B).
- **Q2 (brief, resolved).** First demo instance: City of Vancouver, WA.
- **Q3.** The inventory's VMT is used as published (TR.1.A or TR.1.B). The earlier draft offered both side by side. Is that still wanted, given that most cities have data for only one and the protocol says the two should not be compared?
- **Q4.** Add GPC scope (1, 2, 3) and USCP in-boundary source versus community activity tags (USCP v1.2 Table 1, p.15)? Both depend on facts specific to the city (for example where the landfill is), so they would be instance inputs.
- **Q5. Network access.** Still blocked in the build environment: `github.com` downloads (needed for Python 3.14), `www2.census.gov`, `api.census.gov`, `ofm.wa.gov` and `ecology.wa.gov`. Allowing them would let the demo run in the build environment and replace derived population figures and the illustrative organics share with official ones.
- **Q6.** Should the template carry federal default emission factors (EPA Emission Factors Hub, EPA WARM, DOE) once cited, or always use the factors in the city's inventory? Suggestion: the city's inventory factors for the inventory years, federal defaults only where the inventory gives none (as the demo does for propane).
- **Q7.** Is a zero-effect series acceptable as the "not parameterised" state of an action in the template? The alternative (no values at all) would make the whole model fail whenever any action lacks data.
- **Q8.** Cost parameters: wire per-action costs in USD? In Kausal Paths' unit definitions USD currently has no conversion to EUR, so costs would have to stay in USD throughout.
- **Q9.** Model the emissions of added transit service (for example through a parent action that both cuts car miles and adds bus miles)?
- **Q10 (brief).** Who on the Kausal Paths team should review the structure before it goes further?
- **Q11 (brief).** Should the template live in the kausal-paths repository (here, `configs/modules/uscp/`) or in a separate repository?
- **Q12 (brief).** Should a later version calculate the inventory from raw activity data, or always import the city's published inventory? The template imports published activity data where it exists and totals elsewhere.
- **Q13.** Clean electricity procurement is credited by lowering the emission factor of community electricity. Confirm how each inventory treats renewable energy certificates and community choice aggregation, and whether a location-based figure must be shown alongside.
- **Q14.** The Vancouver inventory report is licensed CC BY-NC-ND 4.0 ("may not be used for any commercial purpose"). The demo uses only numeric figures, with attribution, and reproduces no text or charts. Confirm this is acceptable for a sales demo, or ask the City for permission.
- **Q15.** Replace the demo's illustrative values with cited ones: action trajectories from Vancouver's Climate Action Framework (2022), and sources for electricity per therm displaced, EV electricity per mile, the organics share (Washington Department of Ecology 2020-21 Waste Characterization Study) and a regional urban tree removal factor.
