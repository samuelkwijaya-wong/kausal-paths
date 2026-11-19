# Kausal Paths model template for US communities (USCP-structured inventory)

## Status in one paragraph

This directory holds the structure of the template: the inventory layer, the business-as-usual (BAU) forecast and a library of 24 climate actions, wired so that overlapping actions cannot remove more than the activity they act on. It has **no default numbers yet**. Every default must come with a citation, and the build environment could not open any of the source documents (its network policy blocked the ICLEI USA, EPA, EIA and Pima County hosts). For the same reason there is **no demo instance yet**. The structure has been checked with a static validator; it has not been run in a full Kausal Paths environment. See [Status against the acceptance checks](#status-against-the-acceptance-checks) and [Open questions](#open-questions).

## What the model does

A city loads its own community-wide greenhouse gas inventory, structured by the ICLEI U.S. Community Protocol (USCP). The model:

1. reproduces that inventory in the inventory year, category by category;
2. carries it forward as a BAU forecast using population, jobs, VMT per resident and the grid emission factor trajectory;
3. lets the city switch on actions from its plan, each changing a specific activity or emission factor;
4. reports every result in the inventory's own USCP categories and, through a second tag, in GPC-style sectors (Stationary Energy, Transportation, Waste, IPPU, AFOLU).

Because actions act on the inventory's own categories, the forecast, the inventory and progress reporting use the same structure, with no mapping into a separate set of planning categories.

The model uses a USCP-structured inventory as its input. It does not check, produce or certify an inventory against the protocol.

## Files

| File | Contents |
|---|---|
| `inventory.yaml` | Dimensions `uscp_category` and `gpc_sector`; inventory input nodes; activity x emission factor calculations; BAU projection; reporting node for the USCP basic activities |
| `drivers.yaml` | BAU drivers: population, jobs, VMT per resident, grid emission factor, conversion factors |
| `actions.yaml` | Action library (24 actions), each with a zero-effect series until parameterised |
| `sources.csv` | Source register: every document used or intended, its status and what it supplies |
| `README.md` | This file |

## Inventory categories

Every emissions node carries two tags, as dimensions on `net_emissions`. The category list comes from the project crosswalk brief and the five basic activities named in USCP v1.1 Section 2.2; it still has to be checked against the USCP v1.2 text (open question Q1).

| USCP category (`uscp_category`) | GPC sector (`gpc_sector`) | USCP basic activity | How it is modelled | Instance inputs |
|---|---|---|---|---|
| Residential energy | Stationary energy | Electricity use; fuel combustion | Activity x emission factor, by fuel | Electricity (MWh), natural gas (therms), other fuels (MMBtu) |
| Commercial energy | Stationary energy | Electricity use; fuel combustion | Activity x emission factor, by fuel | As residential |
| Industrial energy | Stationary energy | Electricity use | Activity x emission factor, by fuel | As residential |
| On-road passenger and freight vehicles | Transportation | On-road travel | VMT x emission factor, light-duty and medium/heavy-duty | Total VMT, light-duty share, two emission factors |
| Other transport and mobile sources | Transportation | No | Inventory total | Emissions (t CO2e) |
| Solid waste | Waste | Solid waste generation | Tonnes x emission factor, organics and other materials | Tonnes landfilled, organics share, three emission factors |
| Energy for potable water and wastewater | Stationary energy | Water and wastewater energy | Activity x emission factor | Electricity, natural gas |
| Wastewater treatment process emissions | Waste | No | Inventory total, scaled by population | Emissions (t CO2e) |
| Agriculture (livestock) | AFOLU | No | Inventory total | Emissions (t CO2e) |
| Industrial process and fugitive emissions | IPPU (process); Stationary energy (fugitive) | No | Inventory totals | Two emission totals |
| Forest land and trees | AFOLU | No | Forest: inventory net flux. Trees outside forest: canopy area x removal factor | Net flux, canopy area, removal factor |

Electricity used to charge vehicles that actions electrify is reported under on-road transport (GPC Transportation). Charging that already existed in the inventory year stays inside the building electricity figures, as in most inventories.

## How a city's inventory is loaded

A city gets its own instance file in `configs/`, which includes the three modules and replaces each input node with its own figures. Including with `allow_override: true` means a node the instance defines replaces the template node with the same id completely, so the instance repeats `type`, `quantity` and `unit`.

```yaml
id: example-city
reference_year: 2022            # the inventory year
minimum_historical_year: 2022
maximum_historical_year: 2022   # drivers' historical values must end here
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
  historical_values: [[2022, <value from the inventory>]]
```

Rules for inputs:

- Every node whose description starts with "Instance input" needs a value and a citation in the node description, plus a row in the instance's own copy of the source register.
- Where the inventory reports only a sector total (for example livestock), use the total nodes. Where it reports activity data and emission factors, enter both so actions can act on the activity.
- Drivers (`population`, `jobs`, `vmt_per_capita`, `grid_electricity_emission_factor`) need historical values ending in the inventory year and forecast values after it.
- In the inventory year, activity x emission factor must reproduce the published category totals. Record the tolerance and any difference in the instance description.

The input nodes map one to one onto fields for a future data-entry interface in Kausal Paths; nothing in this template depends on that interface.

## Business-as-usual forecast

Each inventory activity is multiplied by its driver relative to the inventory year (`ratio_to_last_historical_value`), so the inventory year is reproduced exactly:

- residential energy, on-road VMT, solid waste, water and wastewater: population;
- commercial and industrial energy: jobs;
- on-road VMT also: VMT per resident;
- electricity: the grid emission factor trajectory entered by the city;
- vehicles: the light-duty and medium/heavy-duty emission factor forecasts entered by the city.

Other transport, livestock, process, fugitive and forest totals are held at the inventory value.

## Action library

All actions are `simple.AdditiveAction` nodes. Each one's key parameter is a time series by year, which carries the adoption rate, the start year and the target year in one place. **No default has a citation yet, so every default, range and citation below is empty.** Each action ships with a zero-effect series meaning "not parameterised" (open question Q7).

| Action | Inventory category (GPC sector) | Causal path | Parameter (unit) | Default | Range | Citation |
|---|---|---|---|---|---|---|
| Clean electricity procurement | All electricity categories; on-road charging (Stationary energy; Transportation) | Lowers the electricity emission factor | Extra zero-carbon share of community electricity (%) | none | none | none |
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
| Transit bus fleet electrification | On-road | As above, further share | Bus share of medium/heavy-duty VMT x share electrified (%) | none | none | none |
| Organics diversion and composting | Solid waste (Waste) | Moves landfilled organics to composting | Share of landfilled organics diverted (%) | none | none | none |
| Landfill gas capture improvement | Solid waste | Lowers landfill emissions | Reduction in landfill emissions (%) | none | none | none |
| Recycling rate increase | Solid waste | Lowers landfilled other materials | Share diverted (%) | none | none | none |
| Water and wastewater treatment energy efficiency | Water and wastewater energy (Stationary energy) | Lowers utility electricity and gas | Reduction in utility energy (%) | none | none | none |
| Wastewater process emissions reduction | Wastewater process (Waste) | Lowers process emissions | Reduction in process emissions (%) | none | none | none |
| Urban tree canopy expansion | Forest land and trees (AFOLU) | Adds canopy area that removes carbon | Canopy added since inventory year (ha) | none | none | none |

Cost per action (USD) is a key parameter in the brief but is not wired yet (open question Q8).

### How to parameterise an action

Override it in the instance with the city's trajectory, keeping zeros up to the inventory year, and cite every number in its description:

```yaml
actions:
- id: light_duty_ev_adoption
  name: Light-duty electric vehicle adoption
  description: 'Source: <CAP or CCAP>, <publisher>, <year>, <measure table, page>, <URL>.'
  type: simple.AdditiveAction
  group: transportation
  quantity: fraction
  unit: '%'
  historical_values: [[1990, 0], [2022, 0]]
  forecast_values: [[2025, 0], [2030, <value>], [2100, <value>]]
  input_dataset_processors: [LinearInterpolation]
```

### How to add an action

1. Decide which activity or emission factor the action changes. If none fits, add the activity to `inventory.yaml` first; an action should never create emissions outside the inventory categories.
2. Express its effect as either a share of that activity (unit `%`) or an absolute amount in the activity's unit.
3. A share enters the activity's `MultiplicativeNode` as an input with `tags: [complement]`, listed after the activity itself (the first input sets the years). An absolute amount enters as an added input; give that edge `tags: [truncate_before_start, truncate_beyond_end]`, because adding takes the union of years.
4. Decide its order relative to other actions on the same activity and document the overlap (next section).
5. Ship it with `historical_values: [[1990, 0], [2100, 0]]` until a cited default exists, add its parameter to the table above and its sources to `sources.csv`.

## Double counting

The rule: **actions acting on the same activity are combined as sequential factors, never as added reductions.** For shares a, b and c applied to the same activity, the result is activity x (1 - a) x (1 - b) x (1 - c). Each action acts on what the previous ones left, so together they can never remove more than the activity, provided each share stays between 0 and 100%. Kausal Paths does not clamp shares, so the instance must keep them in that range. Results of subtractions (electricity after solar, displaced gas, electric VMT) are only ever subtractions of a smaller quantity from a larger one, and electricity after solar is additionally clipped at zero.

How each overlap is handled:

| Overlap | Handling |
|---|---|
| Mode shift, transit expansion and land use all reduce car travel | Sequential factors on light-duty VMT |
| Demand reduction and EV adoption both reduce gasoline use | EV adoption applies only to the VMT left after demand actions (shared driver: light-duty VMT) |
| EV adoption, public charging and municipal fleet electrification | Sequential factors on the combustion share; each parameter is the share of what remains. If the city's EV figure already assumes the charging buildout, charging stays at zero |
| EV adoption and state vehicle rules in the BAU | The BAU fleet emission factor carries state rules; the EV parameter counts only adoption beyond BAU |
| Medium/heavy-duty ZEVs and transit bus electrification | Sequential factors on the medium/heavy-duty combustion share |
| Retrofits and building performance standard | Sequential factors on commercial energy, retrofits first |
| Efficiency and electrification | Electrification acts on the gas left after efficiency; the displaced gas becomes electricity through one conversion factor |
| Electrification of existing buildings and all-electric new construction | Sequential factors on the remaining gas |
| Electrification and EV charging add electricity; clean procurement lowers its emission factor | Added electricity is counted at the procurement-adjusted factor, so procurement is applied once to all community electricity |
| Local solar and clean procurement | Solar lowers the electricity bought; procurement applies to the rest |
| Grid BAU trajectory and clean procurement | The grid trajectory must exclude the city's own procurement |
| Organics diversion and landfill gas capture | Capture applies to the organics still landfilled |
| Organics diversion and recycling | Act on separate fractions (organics, other materials), each a share of its own fraction |

## Reporting

- **USCP categories:** `net_emissions` by `uscp_category`.
- **GPC sectors:** the same results by `gpc_sector`.
- **USCP basic activities:** node `uscp_basic_activities_emissions`, the sum of the five basic emissions-generating activities. It is a sum of model results, not a statement that the inventory meets the protocol.

## Limitations

- No default values or citations yet; no demo instance; not yet run in a full Kausal Paths environment.
- Category list and the five basic activities not yet checked against the USCP v1.2 text.
- One efficiency share per action applies to all fuels in a sector; electrification applies to natural gas only, not propane or fuel oil.
- Transit service expansion does not add the emissions of the extra service.
- Electric buses use the medium/heavy-duty electricity-per-mile factor.
- Other transport, livestock, process, fugitive and forest emissions are held at the inventory value with no actions.
- One removal factor for all urban canopy, regardless of tree age.
- Harvested wood products and consumption-based emissions are not included.
- Upstream benefits of recycling are outside the inventory and not counted.
- No GPC scope tagging, and no tagging of emissions sources inside the boundary versus community activities (open question Q4).
- The earlier draft `configs/uscp-gpc.yaml` was removed: its placeholder values were typical values without citations, which this brief rules out. Its useful structure (GPC sector tags, the crosswalk) carried over.

## Status against the acceptance checks

| Check | Status |
|---|---|
| Demo instance runs without errors | **Not met.** No demo instance: its data sources could not be opened |
| Baseline totals match the published inventory | **Not met.** Depends on the demo instance |
| Every default has a citation; no uncited numbers | Met by having no defaults. The only numbers are the zero-effect action series (Q7) and the years 1990 and 2100 that bound them |
| Nothing copied from the Transition Element Framework | Met. The TEF repository was not opened; content comes from the project brief and Kausal Paths conventions |
| Actions show effects in the inventory categories and by GPC sector | Met in structure, checked with a static validator; not yet seen in computed results |
| Overlapping actions cannot exceed the underlying activity | Met in structure (sequential factors), as long as each share stays within 0 to 100% |

The static validator merges the include files as the Kausal Paths loader does and checks node references, dimensions and categories, edge tags, and units, including which inputs of each multiplicative node are multiplied and which are added. It was tested by introducing deliberate errors, which it caught.

## Open questions

Questions marked "brief" were raised in the project brief; the rest came up during the build. The numbers are referenced from the YAML files.

- **Q1.** Confirm the `uscp_category` list and labels, the five basic activities and the forest and land use treatment against the USCP v1.2 text and its 2019 appendix.
- **Q2 (brief).** Which city should be the first demo instance? Suggestion: Pima County AZ. Its inventory follows USCP v1.2, its CCAP (November 2025) is public, and it is the documented case of ClearPath 2.0 needing manual mapping, which makes the comparison direct. Whether it is a current prospect is for the sales team to say. If the demo should stay in California, Yolo County (an existing Kausal Paths model) is an alternative, subject to its inventory following the USCP.
- **Q3.** The inventory's VMT is used as published, whichever boundary method the inventory used. The earlier draft offered both the geographic and the origin-destination method side by side. Is that still wanted, given that most cities will have data for only one?
- **Q4.** Add GPC scope (1, 2, 3) and USCP "source inside the boundary versus community activity" tags? Both depend on facts specific to the city (for example where the landfill is), so they would be instance inputs.
- **Q5. Network access (blocking).** The build environment's network policy denied every source host. To continue, allow at least: `icleiusa.org`, `content.civicplus.com`, `www.epa.gov`, `www.eia.gov`, `www.nrel.gov`, `afdc.energy.gov`, `www.census.gov`, `www.orangecountync.gov`, plus the host of whichever city becomes the demo. Then read the USCP, fill `sources.csv`, cite defaults and build the demo instance.
- **Q6.** Should the template carry federal default emission factors (EPA Emission Factors Hub, EPA WARM, DOE) once cited, or always use the factors in the city's inventory? Suggestion: the city's inventory factors for the inventory year, federal defaults only where the inventory gives none.
- **Q7.** Is a zero-effect series acceptable as the "not parameterised" state of an action? The alternative (no values at all) would make the whole model fail whenever any action lacks data.
- **Q8.** Cost parameters: wire per-action costs in USD? In Kausal Paths' unit definitions USD currently has no conversion to EUR, so costs would have to stay in USD throughout.
- **Q9.** Model the emissions of added transit service (for example through a parent action that both cuts car miles and adds bus miles)?
- **Q10 (brief).** Who on the Kausal Paths team should review the structure before it goes further?
- **Q11 (brief).** Should the template live in the kausal-paths repository (here, `configs/modules/uscp/`) or in a separate repository?
- **Q12 (brief).** Should a later version calculate the inventory from raw activity data, or always import the city's published inventory? The template currently imports published activity data where it exists and totals elsewhere.
- **Q13.** Clean electricity procurement is credited by lowering the emission factor of community electricity. Confirm how the chosen inventory treats renewable energy certificates and community choice aggregation, and whether a location-based figure must be shown alongside.
