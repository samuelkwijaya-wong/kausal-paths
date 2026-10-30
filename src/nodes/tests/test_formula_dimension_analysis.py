from __future__ import annotations

import pytest

from nodes.formula import analyze_formula_dimensions

pytestmark = pytest.mark.django_db

DIMS = {'x': {'area', 'hazard'}, 'y': {'area', 'hazard'}, 'z': {'area'}}


@pytest.mark.parametrize(
    'formula',
    ['max(1, x - y)', 'min(x, 1)', 'x >= 3', '3 <= x', 'x - 1', '-1 + x', 'min(min(x >= 3, y >= 3), x >= 3)'],
)
def test_literal_number_applies_to_every_row(formula: str) -> None:
    analysis = analyze_formula_dimensions(formula, DIMS)
    assert analysis.errors == []
    assert analysis.dims == {'area', 'hazard'}


@pytest.mark.parametrize('formula', ['max(x, z)', 'x >= z', 'x - z'])
def test_frames_with_different_dimensions_still_mismatch(formula: str) -> None:
    analysis = analyze_formula_dimensions(formula, DIMS)
    assert any('Dimension mismatch' in err for err in analysis.errors)
