"""
Which city series corresponds to which library series.

Every entry here is a **claim** that two numbers are meant to be the same
factor, and claims can be wrong. They are written down explicitly, one per line,
so that a reviewer can disagree with a particular one rather than with the
comparison as a whole -- and so that a wrong claim shows up as a large reported
difference instead of as a row that quietly went missing.

Two kinds of uncertainty are marked in the ``note`` field and must be resolved
before a result is trusted:

* **The eGRID subregion.** Only Sedona's is documented in its own config
  (``AZNM``, at ``configs/sedona.yaml:251``). The others are inferred from where
  the city is, which is usually right and occasionally not -- a city can sit on a
  subregion boundary, and a municipal utility may draw from a different one than
  its neighbours. Confirm each against EPA's Power Profiler.
* **The dimension category ids.** The city frames' category ids (``co2`` vs
  ``CO2`` vs ``carbon_dioxide``) are not visible from the configs, only the
  dimension names are. Filters here match case-insensitively, but a genuinely
  different id will show up as "not present on one side" rather than as a match.

The node ids, dataset ids, metric columns and units referenced below were read
out of the configs; run ``python -m tools.us_factors.survey`` to see them.
"""

from tools.us_factors.compare import FactorMapping

GASES = ('co2', 'ch4', 'n2o')

SUBREGION_INFERRED = (
    'eGRID subregion inferred from the city location; confirm against EPA Power Profiler.'
)


def _stationary_gas_mappings(
    instance: str,
    city_dataset: str,
    city_metric: str,
    gas_dimension: str,
    fuel: str = 'natural_gas',
    label_prefix: str = '',
) -> list[FactorMapping]:
    """One mapping per gas for a stationary-combustion factor held per gas."""
    return [
        FactorMapping(
            label=f'{label_prefix or instance} {fuel} {gas.upper()}',
            instance=instance,
            city_dataset=city_dataset,
            city_metric=city_metric,
            city_filters={gas_dimension: gas},
            library_dataset='epa_stationary_factors',
            library_filters={'fuel': fuel, 'greenhouse_gas': gas},
        )
        for gas in GASES
    ]


SEDONA: list[FactorMapping] = [
    FactorMapping(
        label='Sedona grid CO2e',
        instance='sedona',
        city_dataset='sedona/grid_emission_factors',
        city_metric='grid_emission_factor',
        # The series varies by electricity_user; the comparison refuses until one
        # is named, because the workbook charges the wastewater plant zero in
        # 2023 and 2024 (configs/sedona.yaml:251) and averaging over that would
        # compare the library against a number no year actually used.
        city_filters={},
        library_dataset='egrid_grid_factors',
        library_filters={'egrid_subregion': 'AZNM', 'greenhouse_gas': 'co2e'},
        note=(
            'AZNM is documented in the config. Expect this to need an '
            'electricity_user filter; run it and the error will name the categories.'
        ),
    ),
    *_stationary_gas_mappings(
        instance='sedona',
        city_dataset='sedona/stationary_emission_factors',
        city_metric='natural_gas_emission_factor',
        gas_dimension='greenhouse_gas',
        label_prefix='Sedona',
    ),
]

MINNEAPOLIS: list[FactorMapping] = [
    FactorMapping(
        label='Minneapolis grid CO2e',
        instance='minneapolis',
        city_dataset='minneapolis/electricity',
        city_metric='emission_factor',
        city_filters={'ghg': 'co2e'},
        library_dataset='egrid_grid_factors',
        library_filters={'egrid_subregion': 'MROW', 'greenhouse_gas': 'co2e'},
        note=SUBREGION_INFERRED,
    ),
]

LONGMONT: list[FactorMapping] = [
    FactorMapping(
        label='Longmont grid CO2e',
        instance='longmont',
        city_dataset='longmont/electricity_emission_factor',
        city_metric='electricity_emission_factor',
        city_filters={},
        library_dataset='egrid_grid_factors',
        library_filters={'egrid_subregion': 'RMPA', 'greenhouse_gas': 'co2e'},
        note=(
            SUBREGION_INFERRED
            + ' Longmont is served by its own municipal utility, so a utility-specific'
            ' factor may legitimately differ from the regional average -- which is'
            ' exactly the case the local override in the shared fragment is for.'
        ),
    ),
]

YOLO: list[FactorMapping] = [
    FactorMapping(
        label='Yolo grid CO2e',
        instance='yolo',
        city_dataset='yolo/energy_emission_factors',
        city_metric='emission_factor',
        city_filters={'ghg': 'co2e', 'energy_carrier': 'electricity'},
        library_dataset='egrid_grid_factors',
        library_filters={'egrid_subregion': 'CAMX', 'greenhouse_gas': 'co2e'},
        note=(
            SUBREGION_INFERRED
            + ' Yolo also carries an energy_provider dimension; the comparison will'
            ' ask for it to be named.'
        ),
    ),
]

ALL_MAPPINGS: list[FactorMapping] = [*SEDONA, *MINNEAPOLIS, *LONGMONT, *YOLO]


def for_instances(instances: set[str] | None = None) -> list[FactorMapping]:
    """Return the mappings for the named instances, or all of them."""
    if instances is None:
        return list(ALL_MAPPINGS)
    return [m for m in ALL_MAPPINGS if m.instance in instances]
