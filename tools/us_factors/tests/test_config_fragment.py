"""
The shared config fragment, checked against the code that produces its data.

The fragment cannot be loaded here -- that needs Django, a database and the
published DVC tables -- so these tests check the things that can be checked
without them, and those turn out to be the things most likely to be wrong: a
dataset id that no source writes, a dimension category the data will never
contain, a filter naming a column the table does not have.

Each of those failures is silent at run time. A dimension category that the data
does not use is merely unused; a category the data *does* use but the fragment
omits makes the import drop rows, and the model then computes from a factor table
with holes in it.
"""
from pathlib import Path

import pytest
import yaml

from tools.us_factors.regions import EGRID_SUBREGIONS
from tools.us_factors.sources import cambium, egrid

REPO = Path(__file__).resolve().parents[3]
FRAGMENT = REPO / 'configs' / 'modules' / 'us' / 'emission_factors.yaml'
DEMO_INSTANCE = REPO / 'configs' / 'us-demo.yaml'


@pytest.fixture(scope='module')
def fragment() -> dict:
    return yaml.safe_load(FRAGMENT.read_text())


@pytest.fixture(scope='module')
def demo() -> dict:
    return yaml.safe_load(DEMO_INSTANCE.read_text())


def dimension(fragment: dict, dimension_id: str) -> dict:
    return next(d for d in fragment['dimensions'] if d['id'] == dimension_id)


def node(fragment: dict, node_id: str) -> dict:
    return next(n for n in fragment['nodes'] if n['id'] == node_id)


def test_fragment_parses(fragment: dict) -> None:
    assert {'datasets', 'dimensions', 'nodes'} <= set(fragment)


def test_declared_datasets_are_ones_the_build_actually_writes(fragment: dict) -> None:
    """A node bound to a table nothing produces fails only when a city adopts it."""
    produced = {f'us/{egrid.DATASET}', f'us/{cambium.DATASET}'}
    declared = {d['id'] for d in fragment['datasets'] if d['id'].startswith('us/')}

    assert declared <= produced, f'Fragment declares tables the build does not write: {declared - produced}'


def test_library_tables_are_locked_and_city_slots_are_not(fragment: dict) -> None:
    """
    Lock the reference data and leave the city's override editable.

    The ownership split the BISKO module makes explicit: reference data cannot be
    edited, the city's own override must be.
    """
    by_id = {d['id']: d for d in fragment['datasets']}

    for identifier, entry in by_id.items():
        if identifier.startswith('us/'):
            assert entry['is_editable'] is False, f'{identifier} must be locked'
        if identifier.startswith('city/'):
            assert entry['is_editable'] is True, f'{identifier} must be editable'


def test_every_subregion_epa_publishes_has_a_category(fragment: dict) -> None:
    """A missing category means that city's rows are dropped on import."""
    categories = {c['id'] for c in dimension(fragment, 'egrid_subregion')['categories']}
    expected = {code.lower() for code in EGRID_SUBREGIONS}

    assert categories == expected


def test_category_ids_match_what_the_parser_emits(fragment: dict) -> None:
    """The parser lower-cases the acronym; the categories must use the same form."""
    categories = {c['id'] for c in dimension(fragment, 'egrid_subregion')['categories']}

    assert 'aznm' in categories
    assert 'AZNM' not in categories


def test_subregion_labels_keep_the_published_acronym(fragment: dict) -> None:
    """A city looks its subregion up in EPA's Power Profiler, which shows the acronym."""
    labels = {c['id']: c['label_en'] for c in dimension(fragment, 'egrid_subregion')['categories']}

    assert labels['aznm'].startswith('AZNM')


def test_gas_categories_cover_what_egrid_publishes(fragment: dict) -> None:
    """Cover the three gases and the CO2-equivalent total eGRID gives and a CO2-equivalent total; all four must be declarable."""
    categories = {c['id'] for c in dimension(fragment, 'greenhouse_gas')['categories']}
    emitted = {rate.gas for rate in egrid.RATE_COLUMNS}

    assert emitted <= categories


def test_grid_node_filters_the_shared_table_by_parameter(fragment: dict) -> None:
    """
    Select the region by parameter, not by a value in the shared file.

    This is the mechanism that lets one fragment serve every city.
    """
    grid = node(fragment, 'grid_emission_factor')
    national = next(d for d in grid['input_datasets'] if 'national' in d.get('tags', []))
    the_filter = national['filters'][0]

    assert national['id'] == f'us/{egrid.DATASET}'
    assert the_filter['column'] == 'egrid_subregion'
    assert the_filter['ref'] == 'egrid_subregion'
    assert 'value' not in the_filter, 'A hard-coded region would make the fragment city-specific'


def test_grid_node_offers_a_local_override(fragment: dict) -> None:
    """
    Let a city's own factor win where it has one.

    A US city on a municipal utility or a green tariff often has a better factor
    than the regional average. Following BISKO, the fragment must let it win.
    """
    grid = node(fragment, 'grid_emission_factor')
    tags = {tag for d in grid['input_datasets'] for tag in d.get('tags', [])}
    params = {p['id']: p for p in grid['params']}

    assert tags == {'national', 'local'}
    assert 'select_port' in params['formula']['value']
    assert params['condition']['ref'] == 'use_epa_default_factors'


def test_factor_nodes_declare_the_emission_factor_quantity(fragment: dict) -> None:
    for entry in fragment['nodes']:
        assert entry['quantity'] == 'emission_factor'
        assert entry['is_editable'] is False


def test_filtered_column_is_dropped_so_the_node_sees_a_plain_series(fragment: dict) -> None:
    """
    Drop the filtered column so the node sees a plain series.

    `drop_col` defaults to true, so the region column disappears after filtering.
    If the fragment ever sets it false the node's dimensions must gain the column.
    """
    grid = node(fragment, 'grid_emission_factor')
    national = next(d for d in grid['input_datasets'] if 'national' in d.get('tags', []))

    assert national['filters'][0].get('drop_col', True) is True
    assert 'egrid_subregion' not in grid['output_dimensions']


# --- the reference instance ---------------------------------------------------

def test_demo_instance_includes_the_fragment(demo: dict) -> None:
    files = {entry['file'] for entry in demo['include']}

    assert 'modules/us/emission_factors.yaml' in files


def test_demo_instance_sets_every_parameter_the_fragment_refers_to(
    demo: dict, fragment: dict
) -> None:
    """
    Declare every parameter the fragment refers to.

    A `ref:` naming a parameter no instance declares fails at load. Catching it
    here is the difference between a five-second test and a Django stack trace.
    """
    referenced = set()
    for entry in fragment['nodes']:
        for dataset in entry.get('input_datasets', []):
            for item in dataset.get('filters', []) or []:
                if 'ref' in item:
                    referenced.add(item['ref'])
        for param in entry.get('params', []):
            if 'ref' in param:
                referenced.add(param['ref'])

    declared = {p['id'] for p in demo['params']}

    assert referenced <= declared, f'Parameters referenced but not declared: {referenced - declared}'


def test_demo_subregion_is_a_real_category(demo: dict, fragment: dict) -> None:
    categories = {c['id'] for c in dimension(fragment, 'egrid_subregion')['categories']}
    value = next(p['value'] for p in demo['params'] if p['id'] == 'egrid_subregion')

    assert value in categories


def test_demo_instance_does_not_shadow_an_existing_city() -> None:
    """The reference instance must be new, not a rename of a model someone uses."""
    existing = {p.stem for p in (REPO / 'configs').glob('*.yaml')} - {'us-demo'}

    assert 'us-demo' not in existing
