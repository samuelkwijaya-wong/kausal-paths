"""
The unit registry, and the two traps it exists to avoid.

These tests pin conversions that a registry built from pint's defaults would get
wrong or refuse. Each is a real unit pairing taken from the US city configs, so a
failure here means the comparison would misreport a real factor.
"""

import pint
import pytest

from tools.us_factors import units


def test_ton_is_metric_as_the_model_defines_it() -> None:
    """Pint's default `ton` is 2000 lb; Paths redefines it as the tonne."""
    assert units.registry().Quantity(1, 'ton').to('kg').magnitude == pytest.approx(1000.0)


def test_short_ton_survives_the_ton_redefinition() -> None:
    """
    A short ton stays 2000 pounds.

    The trap: `short_ton` is an alias of `ton` in pint, so redefining `ton`
    silently turns every US waste factor into tonnes -- a 10.2% error.
    """
    assert units.registry().Quantity(1, 'short_ton').to('kg').magnitude == pytest.approx(907.18474)


@pytest.mark.parametrize(
    ('value', 'source', 'target', 'expected'),
    [
        # Grid factors, as the four US cities actually spell them.
        (1.0, 'lb/MWh', 'kg/MWh', 0.45359237),
        (1.0, 'lbs/MWh', 'lb/MWh', 1.0),
        (1.0, 'lb*CO2e/MWh', 'kg/MWh', 0.45359237),
        (1.0, 't_co2e/MWh', 'lb/MWh', 2204.6226),
        # Stationary combustion.
        (1.0, 'kg/MMBtu', 'g/MMBtu', 1000.0),
        (1.0, 't_co2e/therm', 'kg/therm', 1000.0),
        # Mileage: VMT carries a [vehicle] dimension that must be looked through.
        (1.0, 'g/VMT', 'g/mile', 1.0),
        (1.0, 'g_co2e/mile', 'g/VMT', 1.0),
        # Waste.
        (1.0, 't_co2e/short_ton', 'kg/short_ton', 1000.0),
    ],
)
def test_conversions_used_by_the_comparison(value: float, source: str, target: str, expected: float) -> None:
    assert units.convert(value, source, target) == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize(
    ('source', 'target'),
    [
        ('kg/MWh', 'kg/short_ton'),   # per-energy against per-mass
        ('g/VMT', 'kg/MMBtu'),        # per-distance against per-energy
    ],
)
def test_genuinely_incomparable_units_still_raise(source: str, target: str) -> None:
    """Relaxing the bookkeeping dimensions must not make everything convertible."""
    with pytest.raises(pint.DimensionalityError):
        units.convert(1.0, source, target)


@pytest.mark.parametrize(
    ('unit', 'expected'),
    [
        ('t_co2e/MWh', 't/MWh'),
        ('kg_co2e/gallon', 'kg/gallon'),
        ('g_co2e/mile', 'g/mile'),
        ('lb*CO2e/MWh', 'lb/MWh'),
    ],
)
def test_strip_co2e_leaves_the_physical_unit(unit: str, expected: str) -> None:
    assert units.strip_co2e(unit).replace(' ', '') == expected


def test_relax_reduces_vehicle_distance_to_plain_distance() -> None:
    assert 'mile' in units.relax('g/VMT')
    assert 'VMT' not in units.relax('g/VMT')


def test_definitions_are_read_from_the_model_not_copied() -> None:
    """
    Definitions come from the model, not a copy.

    The registry's contents come from src/nodes/units.py. If that file moves or
    is restructured this fails loudly, rather than the comparison quietly running
    on a stale private copy of the unit definitions.
    """
    text = units.read_definitions()

    assert 'short_ton' in text
    assert 'CO2e' in text
    assert 'VMT' in text


def test_a_missing_definitions_file_is_an_error_not_a_fallback(tmp_path) -> None:
    with pytest.raises(units.UnitDefinitionsNotFoundError):
        units.read_definitions(tmp_path / 'nope.py')


def test_an_unparseable_definitions_file_is_an_error(tmp_path) -> None:
    path = tmp_path / 'units.py'
    path.write_text('# no DEFINITIONS block here\n')

    with pytest.raises(units.UnitDefinitionsNotFoundError, match='restructured'):
        units.read_definitions(path)
