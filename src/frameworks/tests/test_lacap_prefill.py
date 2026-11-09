from __future__ import annotations

import pytest

from frameworks.lacap_prefill import NOTE_PREFIX, write_defaults
from frameworks.models import Measure, MeasureDataPoint, MeasureTemplate, Section
from frameworks.tests.factories import FrameworkConfigFactory

pytestmark = pytest.mark.django_db


def test_write_defaults_sets_default_and_keeps_city_value() -> None:
    fwc = FrameworkConfigFactory.create(baseline_year=2018)
    section = Section.add_root(instance=Section(framework=fwc.framework, name='Root'))
    heat = MeasureTemplate.objects.create(section=section, name='Heat', unit='GWh/a')
    electricity = MeasureTemplate.objects.create(section=section, name='Electricity', unit='GWh/a')
    measure = Measure.objects.create(framework_config=fwc, measure_template=electricity, internal_notes='Checked by city')
    MeasureDataPoint.objects.create(measure=measure, year=2018, value=2100.0, default_value=1500.0)

    results = write_defaults(
        fwc,
        2018,
        {'building_heat': heat, 'electricity': electricity},
        {'building_heat': 3078.2, 'electricity': 1991.1},
        source='ie-lacap-dublin',
    )

    heat_dp = MeasureDataPoint.objects.get(measure__framework_config=fwc, measure__measure_template=heat, year=2018)
    assert heat_dp.default_value == 3078.2
    assert heat_dp.value is None

    el_dp = MeasureDataPoint.objects.get(measure=measure, year=2018)
    assert el_dp.default_value == 1991.1
    assert el_dp.value == 2100.0  # the city's own value is kept

    by_field = {r.field: r for r in results}
    assert by_field['electricity'].previous_default == 1500.0
    assert by_field['electricity'].city_value == 2100.0

    measure.refresh_from_db()
    assert measure.internal_notes.splitlines()[0] == 'Checked by city'
    assert measure.internal_notes.splitlines()[1].startswith(NOTE_PREFIX)


def test_write_defaults_replaces_previous_prefill_note() -> None:
    fwc = FrameworkConfigFactory.create(baseline_year=2018)
    section = Section.add_root(instance=Section(framework=fwc.framework, name='Root'))
    other = MeasureTemplate.objects.create(section=section, name='Other sectors', unit='kt/a')

    write_defaults(fwc, 2018, {'other_sectors': other}, {'other_sectors': 70.0}, source='a')
    write_defaults(fwc, 2018, {'other_sectors': other}, {'other_sectors': 76.4}, source='b')

    measure = Measure.objects.get(framework_config=fwc, measure_template=other)
    assert measure.internal_notes.count(NOTE_PREFIX) == 1
    assert '(b, 2018)' in measure.internal_notes
    assert measure.data_points.get(year=2018).default_value == 76.4
