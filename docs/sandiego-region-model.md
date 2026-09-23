# San Diego region model (`sandiego-region`)

A draft model of the San Diego Regional Climate Action Roadmap (SANDAG, December 2025). It
reproduces the greenhouse gas calculations in the Roadmap's technical appendices, which were
prepared by the Energy Policy Initiatives Center (EPIC) at the University of San Diego:

- **Appendix B**: 2022 regional inventory (14 categories).
- **Appendix D**: business-as-usual projections for 2035 and 2045.
- **Appendix E**: the implementation scenario, i.e. Roadmap measures and California Scoping Plan goals.

| File | Contents |
|---|---|
| `configs/sandiego-region.yaml` | the model. It is generated, so do not edit it by hand. |
| `notebooks/sandiego_region/generate_config.py` | writes the model. Every input number and every derived value is here, with its source table. |
| `notebooks/sandiego_region/verify_model.py` | compares the model's output with the appendix figures. |

```bash
python notebooks/sandiego_region/generate_config.py configs/sandiego-region.yaml
python notebooks/sandiego_region/verify_model.py configs/sandiego-region.yaml
python load_nodes.py -c configs/sandiego-region.yaml --node net_emissions
```

## Status

This is a first draft. The numbers are inline `historical_values` / `forecast_values`. They should
move into datasets before a city or regional user works with the model. Only three data years
exist in the appendices (2022, 2035, 2045), so the years in between are straight-line
interpolation.

## Scenarios

- **`baseline`: legislatively-adjusted business as usual (Appendix D).** Adopted state and
  federal legislation is modelled as actions in the `state_federal` group. They are enabled in
  this scenario:
  - SB 100 / SB 1020 and the CCA commitments act on each provider's electricity emission factor.
  - The EMFAC2025 vehicle rules act on the on-road emission factor.
  - SB 1383 acts on waste tonnage and composition.
  - Landfill methane capture is raised to 85 %.

  The underlying activity forecasts are the ones EPIC used (SANDAG VMT, the CEC demand forecast,
  OFFROAD2021, airport and water-authority forecasts). They are node data, not actions.
- **`default`: Roadmap implementation scenario (Appendix E).** All actions on:
  - 13 quantified Roadmap measures (T-1…T-6, E-1, B-1/B-2, IND-1, SW-1, SW-2, WW-1/WW-2, WW-3, AG-1)
  - 6 Scoping Plan goals
  - the unquantified measures (IND-2, AG-2…AG-4, NWL-1…NWL-3), as zero-effect actions
- **No-Action BAU.** EPIC defines this as 2022 emissions per person × population. It is the
  `no_action_bau_emissions` reference node, not a scenario.

## Method choices

- Each category is an activity × emission factor chain where Appendix B gives one: on-road,
  electricity by provider, natural gas, solid waste, water. Otherwise it is the 2022 value grown
  with the SANDAG driver EPIC names (industrial, other fuels, wastewater). Otherwise it is the
  appendix value itself (off-road, marine, aviation, agriculture, rail).
- Electricity used by water treatment and electric rail is subtracted from the electricity
  category, as in Appendix B. Gas used for on-site self-generation is counted under electricity.
- Measures that change activity or intensity act on that node. VMT measures act on VMT; T-5 acts
  on the vehicle emission factor. VMT avoided is back-calculated from EPIC's tonnes at the
  implementation-scenario emission factor.

  Where Appendix E gives only tonnes, the measure is an absolute change on the category
  (T-6, E-1, IND-1, WW-3, AG-1 and the Scoping Plan goals).
- EPIC estimated each measure against the adjusted BAU on its own. Paths computes them together,
  so overlapping measures credit slightly less than the standalone figures:
  - T-5 with the VMT measures
  - SW-1 with SW-2

  `verify_model.py` prints both.
- The 2035 and 2045 targets follow Appendix D's category detail tables (D.4–D.18).

## Still needed

- SANDAG Draft 2025 Regional Plan: the Build vs. No-Build VMT difference. The `regional_plan_2025`
  action is a zero placeholder until this is available.
- The Roadmap's 2035 and 2045 goal values (for a goal line).
- Year-by-year source runs (EMFAC2025, CEC IEPR, OFFROAD2021) if annual detail is wanted.
