"""
The library-vs-city comparison.

The four outcomes are tested separately because they carry different meanings
and the last two are the ones that matter most in practice: "could not be
compared" and "present on only one side" are findings, and a comparison that
collapsed them into "differs" or dropped them would hide the very things it is
run to discover.
"""

import polars as pl
import pytest

from tools.us_factors.compare import (
    AmbiguousSeriesError,
    FactorMapping,
    Verdict,
    compare_all,
    compare_one,
    format_report,
    summarise,
)


def library_frame(**overrides) -> pl.DataFrame:
    base = {
        'dataset': ['egrid_grid_factors'] * 2,
        'metric': ['grid_emission_factor'] * 2,
        'unit': ['lb/MWh'] * 2,
        'egrid_subregion': ['AZNM'] * 2,
        'greenhouse_gas': ['co2e'] * 2,
        'year': [2022, 2023],
        'value': [700.0, 690.0],
    }
    base.update(overrides)
    return pl.DataFrame(base, schema_overrides={'year': pl.Int32})


def city_frame(**overrides) -> pl.DataFrame:
    base = {
        'dataset': ['sedona/grid_emission_factors'] * 2,
        'metric': ['grid_emission_factor'] * 2,
        'unit': ['lb*CO2e/MWh'] * 2,
        'year': [2022, 2023],
        'value': [700.0, 690.0],
    }
    base.update(overrides)
    return pl.DataFrame(base, schema_overrides={'year': pl.Int32})


MAPPING = FactorMapping(
    label='Sedona grid CO2e',
    instance='sedona',
    city_dataset='sedona/grid_emission_factors',
    city_metric='grid_emission_factor',
    library_dataset='egrid_grid_factors',
    library_filters={'egrid_subregion': 'AZNM', 'greenhouse_gas': 'co2e'},
)


def test_identical_values_agree() -> None:
    report = compare_one(library_frame(), city_frame(), MAPPING)

    assert report['verdict'].unique().to_list() == [Verdict.AGREES]


def test_agreement_survives_a_unit_difference() -> None:
    """The city writes lb*CO2e/MWh, the library lb/MWh; the numbers still match."""
    report = compare_one(library_frame(), city_frame(), MAPPING)

    assert report['library_in_city_unit'].to_list() == [700.0, 690.0]


def test_a_real_difference_is_reported_with_its_size() -> None:
    city = city_frame(value=[700.0, 600.0])

    report = compare_one(library_frame(), city, MAPPING)

    differing = report.filter(pl.col('verdict') == Verdict.DIFFERS)
    assert differing.height == 1
    assert differing['year'].item() == 2023
    assert differing['difference'].item() == pytest.approx(90.0)
    assert differing['relative_difference'].item() == pytest.approx(0.15)


def test_rounding_within_tolerance_still_agrees() -> None:
    """A city that rounded on the way in has not actually disagreed."""
    city = city_frame(value=[700.2, 690.0])

    report = compare_one(library_frame(), city, MAPPING)

    assert report['verdict'].unique().to_list() == [Verdict.AGREES]


def test_tolerance_is_configurable() -> None:
    city = city_frame(value=[700.2, 690.0])

    report = compare_one(library_frame(), city, MAPPING, tolerance=0.0)

    assert Verdict.DIFFERS in report['verdict'].to_list()


def test_converts_across_a_real_unit_change() -> None:
    """A city holding tonnes per MWh against a library in pounds per MWh."""
    city = city_frame(unit=['t_co2e/MWh'] * 2, value=[0.3175, 0.3130])

    report = compare_one(library_frame(), city, MAPPING)

    # 700 lb = 0.31751 t, so the 2022 row should agree.
    assert report.filter(pl.col('year') == 2022)['verdict'].item() == Verdict.AGREES


def test_incomparable_units_are_reported_not_silently_dropped() -> None:
    """A mass-per-energy factor against a mass-per-mass one cannot be compared."""
    city = city_frame(unit=['t_co2e/short_ton'] * 2)

    report = compare_one(library_frame(), city, MAPPING)

    assert report['verdict'].unique().to_list() == [Verdict.INCOMPARABLE]
    assert report['difference'].null_count() == 2


def test_a_year_only_the_city_has_is_flagged() -> None:
    city = city_frame(year=[2022, 2023, 2024], value=[700.0, 690.0, 680.0],
                      dataset=['sedona/grid_emission_factors'] * 3,
                      metric=['grid_emission_factor'] * 3,
                      unit=['lb*CO2e/MWh'] * 3)

    report = compare_one(library_frame(), city, MAPPING)

    assert report.filter(pl.col('year') == 2024)['verdict'].item() == Verdict.CITY_ONLY


def test_a_year_only_the_library_has_is_flagged() -> None:
    city = city_frame(year=[2022], value=[700.0], dataset=['sedona/grid_emission_factors'],
                      metric=['grid_emission_factor'], unit=['lb*CO2e/MWh'])

    report = compare_one(library_frame(), city, MAPPING)

    assert report.filter(pl.col('year') == 2023)['verdict'].item() == Verdict.LIBRARY_ONLY


def test_library_filters_select_the_right_region() -> None:
    """Picking the wrong subregion must not silently compare against it."""
    library = pl.concat([
        library_frame(),
        library_frame(egrid_subregion=['CAMX'] * 2, value=[100.0, 110.0]),
    ], how='vertical')

    report = compare_one(library, city_frame(), MAPPING)

    assert report['verdict'].unique().to_list() == [Verdict.AGREES]
    assert report['library_value'].to_list() == [700.0, 690.0]


def test_an_unreduced_dimension_refuses_rather_than_picking_a_row() -> None:
    """
    Refuse when a dimension is left unreduced.

    Sedona's grid factor varies by `electricity_user` -- its wastewater plant is
    charged zero in some years. Comparing against an arbitrary one of those would
    report agreement or disagreement depending on row order.
    """
    city = pl.DataFrame({
        'dataset': ['sedona/grid_emission_factors'] * 4,
        'metric': ['grid_emission_factor'] * 4,
        'unit': ['lb*CO2e/MWh'] * 4,
        'electricity_user': ['general', 'wastewater', 'general', 'wastewater'],
        'year': [2022, 2022, 2023, 2023],
        'value': [700.0, 700.0, 690.0, 0.0],
    }, schema_overrides={'year': pl.Int32})

    with pytest.raises(AmbiguousSeriesError, match='electricity_user'):
        compare_one(library_frame(), city, MAPPING)


def test_naming_the_dimension_resolves_the_ambiguity() -> None:
    city = pl.DataFrame({
        'dataset': ['sedona/grid_emission_factors'] * 4,
        'metric': ['grid_emission_factor'] * 4,
        'unit': ['lb*CO2e/MWh'] * 4,
        'electricity_user': ['general', 'wastewater', 'general', 'wastewater'],
        'year': [2022, 2022, 2023, 2023],
        'value': [700.0, 700.0, 690.0, 0.0],
    }, schema_overrides={'year': pl.Int32})
    mapping = FactorMapping(
        label='Sedona grid CO2e (general)',
        instance='sedona',
        city_dataset='sedona/grid_emission_factors',
        city_metric='grid_emission_factor',
        city_filters={'electricity_user': 'general'},
        library_dataset='egrid_grid_factors',
        library_filters={'egrid_subregion': 'AZNM', 'greenhouse_gas': 'co2e'},
    )

    report = compare_one(library_frame(), city, mapping)

    assert report['verdict'].unique().to_list() == [Verdict.AGREES]


def test_duplicate_years_with_no_distinguishing_dimension_also_refuse() -> None:
    city = city_frame(year=[2022, 2022], value=[700.0, 500.0])

    with pytest.raises(AmbiguousSeriesError, match='more than one value'):
        compare_one(library_frame(), city, MAPPING)


def test_a_mapping_without_an_export_is_skipped_not_failed() -> None:
    """Not having looked is different from having looked and found nothing."""
    report = compare_all(library_frame(), {}, [MAPPING])

    assert report.is_empty()


def test_compare_all_covers_several_cities() -> None:
    other = FactorMapping(
        label='Other city grid',
        instance='other',
        city_dataset='other/grid',
        city_metric='grid_emission_factor',
        library_dataset='egrid_grid_factors',
        library_filters={'egrid_subregion': 'AZNM', 'greenhouse_gas': 'co2e'},
    )
    frames = {
        'sedona': city_frame(),
        'other': city_frame(dataset=['other/grid'] * 2, value=[1.0, 1.0]),
    }

    report = compare_all(library_frame(), frames, [MAPPING, other])

    assert set(report['instance'].unique()) == {'sedona', 'other'}
    assert Verdict.DIFFERS in report.filter(pl.col('instance') == 'other')['verdict'].to_list()


def test_summary_puts_disagreements_first() -> None:
    city = city_frame(value=[700.0, 600.0])

    summary = summarise(compare_one(library_frame(), city, MAPPING))

    assert summary['verdict'].to_list()[0] == Verdict.DIFFERS


def test_report_leads_with_the_problems() -> None:
    city = city_frame(value=[700.0, 600.0])

    text = format_report(compare_one(library_frame(), city, MAPPING))

    assert 'Disagreements and gaps' in text
    assert '15.0%' in text


def test_report_says_so_when_everything_agrees() -> None:
    text = format_report(compare_one(library_frame(), city_frame(), MAPPING))

    assert 'agrees with the library' in text


def test_empty_comparison_says_nothing_was_compared() -> None:
    assert 'Nothing compared' in format_report(compare_all(library_frame(), {}, [MAPPING]))
