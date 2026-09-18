"""
A pint registry that matches the model's, without importing the model.

The comparison has to convert between the units cities actually wrote --
``lb*CO2e/MWh``, ``t_co2e/MWh``, ``lbs/MWh``, ``g/VMT``, ``t/short_ton`` -- and
those are not all standard pint. Several are defined by Paths itself, and two of
them are traps:

* ``ton`` is redefined as the **metric** tonne, and ``short_ton`` is defined
  separately as 2000 pounds. Pint's defaults have it the other way round, so a
  registry built from pint's defaults reads every US waste factor 10.2% wrong.
* ``CO2e`` is its own dimension. ``t_co2e`` is ``tonne * CO2e``, so
  ``lb*CO2e/MWh`` and ``lb/MWh`` are **not** interconvertible without saying
  what the CO2e marker means. The comparison handles that explicitly rather than
  letting a conversion silently fail or silently succeed.

Rather than copy those definitions -- which would drift the first time someone
edits the model's registry -- this module reads the authoritative block out of
``src/nodes/units.py`` at import time. That file cannot simply be imported here:
it pulls in pydantic, loguru and platformdirs and expects the application stack,
while this tool must run as a plain script against exported CSVs.
"""

import re
from pathlib import Path

import pint

UNITS_SOURCE = Path(__file__).resolve().parents[2] / 'src' / 'nodes' / 'units.py'

STALE_ALIASES = ('short_ton', 'US_ton')
"""
Aliases of pint's ``ton`` that must be removed before ``ton`` is redefined.

Mirrors ``define_custom_units`` in the model's registry: both are aliases rather
than independent definitions, so redefining ``ton`` as the tonne drags them with
it and ``short_ton`` silently becomes a metric tonne.
"""


class UnitDefinitionsNotFoundError(RuntimeError):
    """The model's unit definitions could not be located, so no registry is built."""


def read_definitions(source: Path = UNITS_SOURCE) -> str:
    """Extract the ``DEFINITIONS`` block from the model's unit module."""
    if not source.exists():
        raise UnitDefinitionsNotFoundError(f'Model unit definitions not found at {source}')
    text = source.read_text()
    match = re.search(r'\n    DEFINITIONS = """\n(.*?)\n    """', text, re.DOTALL)
    if match is None:
        raise UnitDefinitionsNotFoundError(
            f'No DEFINITIONS block in {source}. The model registry has been restructured; '
            'this loader must be updated rather than guessed around.'
        )
    return match.group(1)


def build_registry(source: Path = UNITS_SOURCE) -> pint.UnitRegistry:
    """Build a registry carrying the model's custom units."""
    ureg = pint.UnitRegistry()

    # Same order as define_custom_units: clear the names that are about to be
    # redefined, including the case-insensitive entries, or pint refuses.
    for name in ('kt', 'ton'):
        ureg._units.pop(name, None)
    for stale in STALE_ALIASES:
        ureg._units.pop(stale, None)
        ureg._units_casei.get(stale.lower(), set()).discard(stale)

    for line in read_definitions(source).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        try:
            ureg.define(stripped)
        except (pint.PintError, ValueError, TypeError, AttributeError):
            # The model's block contains entries this bare registry cannot take
            # (currency placeholders defined as nan, for instance). Skipping one
            # is safe: the tests pin every unit the comparison actually needs, so
            # a definition that mattered would fail there rather than here.
            continue
    return ureg


_REGISTRY: pint.UnitRegistry | None = None


def registry() -> pint.UnitRegistry:
    """Return the shared registry, building it on first use."""
    global _REGISTRY  # noqa: PLW0603 - one process-wide registry, as pint requires
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY


def strip_co2e(unit: str) -> str:
    """
    Remove the CO2e marker from a unit string.

    ``CO2e`` is a dimension in the model registry, which is what stops a
    CO2-equivalent quantity being silently added to a plain mass. For comparing
    two numbers that both mean "CO2-equivalent mass", though, the marker is
    exactly what has to come off -- and doing it by an explicit, named step
    keeps that decision visible instead of hiding it in a conversion.
    """
    text = re.sub(r'\b(k|kilo)?t_?co2e\b', lambda m: f'{m.group(1) or ""}t', unit, flags=re.IGNORECASE)
    text = re.sub(r'\b(k|m|g|u)?g_?co2e\b', lambda m: f'{m.group(1) or ""}g', text, flags=re.IGNORECASE)
    text = re.sub(r'\*?\s*CO2e\s*\*?', '', text, flags=re.IGNORECASE)
    return text.strip().strip('*').strip() or 'dimensionless'


VEHICLE_DISTANCE_UNITS = {
    'VMT': 'mile',
    'vehicle_miles_traveled': 'mile',
    'vkm': 'km',
    'vehicle_km': 'km',
    'v_km': 'km',
    'vkt': 'km',
}
"""
Per-vehicle distance units, and the plain distance each reduces to.

``VMT`` is ``vehicle * mile``, carrying a ``[vehicle]`` dimension that keeps a
per-vehicle factor from being mistaken for a per-distance one. Cities write
mileage factors in ``g/VMT``; EPA publishes the same quantity as grams per mile.
Comparing them means looking through that dimension, which is done here by an
explicit substitution rather than by a conversion that might quietly succeed for
the wrong reason.
"""


def normalise_spelling(unit: str) -> str:
    """Fix the spellings cities use that pint does not accept, such as ``lbs``."""
    return re.sub(r'\blbs\b', 'lb', unit.strip().strip('\'"'))


def relax(unit: str) -> str:
    """
    Drop the bookkeeping dimensions, leaving only the physical quantity.

    Used only as a second attempt, after an exact conversion has failed, so that
    a genuine mismatch is never hidden by it.
    """
    text = strip_co2e(normalise_spelling(unit))
    for marker, plain in VEHICLE_DISTANCE_UNITS.items():
        text = re.sub(rf'\b{re.escape(marker)}\b', plain, text)
    return text


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """
    Convert ``value`` between two unit strings as the model understands them.

    Raises ``pint.DimensionalityError`` when the two are genuinely incomparable,
    which the comparison reports rather than suppresses -- a factor that cannot
    be compared is a finding, not a blank.
    """
    ureg = registry()
    src = normalise_spelling(from_unit)
    dst = normalise_spelling(to_unit)
    try:
        return float(ureg.Quantity(value, src).to(dst).magnitude)
    except pint.DimensionalityError:
        # Retry with the bookkeeping dimensions removed from both sides:
        # comparing a co2e-tagged or per-vehicle factor against a plain one is
        # the common case, and neither marker is a physical dimension.
        return float(ureg.Quantity(value, relax(src)).to(relax(dst)).magnitude)
