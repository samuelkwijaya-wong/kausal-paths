# Banff demo - summary for Samuel

Illustrative demo based on the public 2019 Banff Renewable Energy Transition Roadmap.
Not prepared or endorsed by the Town of Banff.

## What was built

A small Paths model of Banff, built only from the public Roadmap.

- **2016 inventory** by GPC sector: 425,080 t CO2e.
- **Three scenarios**: no change from 2016 (a reference line), business as usual (292,160 t in
  2050) and the Roadmap (71,884 t in 2050). The model reproduces the Roadmap's published 2050
  figures sector by sector, to the tonne.
- **Actions sorted the way the RFP asks**: (a) changes that happen regardless of local action
  (cleaner Alberta grid, vehicle efficiency, waste and gas network trends); (b) necessary local
  actions (electrify visitor vehicles, enhanced transit, non-residential retrofits); (c) choices
  to weigh (gas cogeneration, buying renewable electricity); and one block for the other 21 rows of
  the Roadmap's action table. Each of the five named actions has exactly the 2050 effect the Roadmap
  publishes. This sorting is our proposal for discussion, not the Town's.
- **Visitors**: residents, day and multi-day visitors, and the visitor-adjusted population
  (about 23,900 in 2016, 33,400 in 2050).
- **Emissions efficiency**: per resident (45 t in 2016), per visitor-adjusted person (18 t) and
  visitor transport per visit (41 kg).
- **2016 and 2026 side by side**. As agreed, the 2026 column holds placeholder values: the
  Roadmap's own business-as-usual forecast for 2026, labelled as a placeholder everywhere. The
  real 2026 inventory replaces it later.
- **The Town's target line**: 30% below 2016 by 2030, 80% by 2050.
- Every number carries a note saying which Roadmap page it comes from, and whether it is exact,
  read from a chart or interpolated.

## Best screens for CEA

1. The home page with the scenario switch: business as usual against the Roadmap, with the
   target line.
2. The action list, grouped (a), (b), (c), showing what each action is worth.
3. "2016 and 2026 inventories", which shows the Phase 1 reconciliation slot.
4. "Emissions efficiency" and "Residents and visitors", which cover the RFP's new measures and
   visitor focus.

## What was simplified

- The model is matched to the Roadmap's results; it does not rebuild buildings, vehicles or
  energy flows. The Roadmap says its actions depend on each other, so switching one off alone
  is an approximation.
- The Roadmap does not say which sectors each action reduces, or how fast. We split and timed
  them by simple, written-down rules that still add up to the Roadmap's published totals.
- Energy use is shown for business as usual only.

## What is still missing

- Emissions per tourism dollar and per unit of economic output: the Roadmap has no revenue or
  economic data. These, plus building numbers, transit ridership and air travel, are blank rows
  in a 2026 data template.
- Costs and the marginal abatement chart.
- The 21 smaller rows of the Roadmap's action table as separate switches.
- I have not seen the screens themselves. The model was run and checked here, but the
  instance can only be viewed once Jouni has uploaded the data and set it up.

## Decisions I made from the brief's questions (change any of them)

- Instance name: "Banff (illustrative demo)".
- "Per tourism dollar": left out of the model as a number, kept as a blank row in the template.
- First version: the five largest actions plus one block for the rest.
- Hosting and timing: for you and Jouni. Everything he needs is in `SETUP_FOR_JOUNI.md`.

The Roadmap disagrees with itself in 12 places (for example, a renewable share of 54% or 48% in
2050). They are listed in `DATA_NOTES.md` and do not change the emissions totals.
