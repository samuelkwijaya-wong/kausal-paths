"""
The config survey.

Two kinds of test here. The first work against small synthetic configs and pin
the parsing rules. The last run against the repository's real configs -- not to
assert particular numbers, which would break every time a city model is edited,
but to assert that the survey still finds something and still reports the
duplication it exists to expose. A survey that silently returned nothing would
otherwise look like good news.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations` in new
# files, and without it the flake8-type-checking fixes are not available.



from pathlib import Path

import pytest
import yaml

from tools.us_factors import survey


def write_config(tmp_path: Path, name: str, nodes: list[dict], **extra: object) -> Path:
    doc = {'id': name, 'nodes': nodes}
    doc.update(extra)
    path = tmp_path / f'{name}.yaml'
    path.write_text(yaml.safe_dump(doc))
    return path


def test_finds_only_emission_factor_nodes(tmp_path: Path) -> None:
    path = write_config(tmp_path, 'city', [
        {'id': 'grid_ef', 'quantity': 'emission_factor', 'unit': 'lb/MWh'},
        {'id': 'consumption', 'quantity': 'energy', 'unit': 'kWh/a'},
    ])

    found = survey.survey_config(path)

    assert [n.node_id for n in found] == ['grid_ef']


def test_records_unit_dimensions_and_datasets(tmp_path: Path) -> None:
    path = write_config(tmp_path, 'city', [{
        'id': 'grid_ef',
        'quantity': 'emission_factor',
        'unit': 'lb*CO2e/MWh',
        'input_dimensions': ['electricity_user'],
        'input_datasets': [{'id': 'city/grid_emission_factors', 'column': 'grid_emission_factor'}],
    }])

    node = survey.survey_config(path)[0]

    assert node.unit == 'lb*CO2e/MWh'
    assert node.dimensions == ('electricity_user',)
    assert node.datasets == (('city/grid_emission_factors', 'grid_emission_factor'),)
    assert node.namespaces == ('city',)


def test_handles_a_bare_string_dataset_reference(tmp_path: Path) -> None:
    """``input_datasets`` entries may be plain ids as well as mappings."""
    path = write_config(tmp_path, 'city', [{
        'id': 'ef',
        'quantity': 'emission_factor',
        'input_datasets': ['city/factors'],
    }])

    node = survey.survey_config(path)[0]

    assert node.datasets == (('city/factors', None),)


def test_a_derived_node_with_no_dataset_is_still_reported(tmp_path: Path) -> None:
    """Computed factor nodes carry no dataset; omitting them would understate the model."""
    path = write_config(tmp_path, 'city', [
        {'id': 'ef_co2e', 'quantity': 'emission_factor', 'unit': 't_co2e/MWh'},
    ])

    node = survey.survey_config(path)[0]

    assert node.datasets == ()
    assert node.namespaces == ()


def test_uses_the_declared_instance_id_not_the_filename(tmp_path: Path) -> None:
    path = tmp_path / 'file-name.yaml'
    path.write_text(yaml.safe_dump({'id': 'declared-id', 'nodes': [
        {'id': 'ef', 'quantity': 'emission_factor'},
    ]}))

    assert survey.survey_config(path)[0].instance == 'declared-id'


def test_missing_configs_are_reported_not_skipped_silently(tmp_path: Path) -> None:
    write_config(tmp_path, 'present', [{'id': 'ef', 'quantity': 'emission_factor'}])

    result = survey.run(('present', 'absent'), config_dir=tmp_path)

    assert result.missing == ['absent']
    assert len(result.nodes) == 1


def test_shared_namespaces_finds_a_namespace_used_by_two_cities(tmp_path: Path) -> None:
    for city in ('a', 'b'):
        write_config(tmp_path, city, [{
            'id': 'ef',
            'quantity': 'emission_factor',
            'input_datasets': [{'id': 'us/egrid_grid_factors'}, {'id': f'{city}/local'}],
        }])

    result = survey.run(('a', 'b'), config_dir=tmp_path)

    assert result.shared_namespaces() == {'us'}


@pytest.mark.parametrize(
    ('unit', 'expected'),
    [
        ('lb*CO2e/MWh', 'lb/mwh'),
        ('lbs/MWh', 'lb/mwh'),
        ('t_co2e/MWh', 't/mwh'),
        ('t/MWh', 't/mwh'),
        ('kg_co2e/MMBtu', 'kg/mmbtu'),
        ('kg/MMBtu', 'kg/mmbtu'),
        (None, '<none>'),
    ],
)
def test_unit_normalisation_groups_equivalent_spellings(unit: str | None, expected: str) -> None:
    """The point of the fold: three spellings of one quantity must land together."""
    assert survey._normalise_unit(unit) == expected


# --- against the real repository configs -------------------------------------

def test_the_real_configs_still_yield_a_survey() -> None:
    result = survey.run()

    assert not result.missing, f'US instance configs have moved or been renamed: {result.missing}'
    assert len(result.nodes) > 50, 'Expected many factor nodes across the US instances'


def test_the_duplication_this_library_addresses_is_still_present() -> None:
    """
    The per-city duplication is still present.

    Guard the premise. If US cities ever do share a factor namespace, this test
    fails and the library's justification needs rewriting -- which is a good
    reason to be told.
    """
    result = survey.run()

    namespaces = {ns for node in result.nodes for ns in node.namespaces}
    per_city = {ns for ns in namespaces if ns not in {'us', 'gpc', 'nzc'}}

    assert len(per_city) > 1, (
        f'Expected several per-city factor namespaces; found {sorted(namespaces)}'
    )


def test_the_greenhouse_gas_dimension_is_still_spelled_several_ways() -> None:
    """
    The gas dimension is still spelled several ways.

    A concrete piece of the drift, and one the shared fragment will have to
    reconcile: the same dimension is called ``ghg`` in some cities,
    ``greenhouse_gas`` in others and ``greenhouse_gases`` in a third.
    """
    result = survey.run()

    spellings = {
        dim for node in result.nodes for dim in node.dimensions
        if dim.startswith(('ghg', 'greenhouse'))
    }

    assert len(spellings) > 1, f'Expected divergent gas dimension names, found {spellings}'


def test_report_renders_without_error() -> None:
    text = survey.format_report(survey.run())

    assert 'Summary' in text
    assert 'emission-factor nodes' in text
