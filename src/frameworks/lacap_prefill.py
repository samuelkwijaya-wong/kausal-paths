"""
Pre-fill NetZeroCities data collection fields from an Irish LACAP inventory.

An Irish Mission city keeps a LACAP inventory (configs/modules/ie/lacap.yaml) and also fills in the
NetZeroCities form. The LACAP model computes suggested values for three form fields; this module writes
them as the city's ``MeasureDataPoint.default_value`` for one year. A value the city has entered
(``MeasureDataPoint.value``) is never changed and always wins over the default.

Passenger-km and freight tonne-km are deliberately not suggested: they count trips, which the
fuel-based inventory cannot give without guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction

import polars as pl

from frameworks.models import Measure, MeasureDataPoint, MeasureTemplate

if TYPE_CHECKING:
    from pathlib import Path

    from frameworks.models import FrameworkConfig
    from nodes.context import Context

# Form field (command option name) -> LACAP model node that computes the suggestion.
SUGGESTION_NODES: dict[str, str] = {
    'building_heat': 'nzc_suggested_building_heat',
    'electricity': 'nzc_suggested_electricity',
    'other_sectors': 'nzc_suggested_other_sectors',
}

NOTE_PREFIX = 'Default pre-filled from the LACAP inventory'


@dataclass
class PrefillResult:
    field: str
    template: MeasureTemplate
    year: int
    default_value: float
    previous_default: float | None
    city_value: float | None


def compute_suggestions(context: Context, year: int, templates: dict[str, MeasureTemplate]) -> dict[str, float]:
    """Return the suggested value for each field, in the unit of its form field."""
    values: dict[str, float] = {}
    for field, template in templates.items():
        node = context.get_node(SUGGESTION_NODES[field])
        df = node.get_output_pl()
        metric = df.metric_cols[0]
        other_dims = [col for col in df.primary_keys if col != 'Year']
        if other_dims:
            df = df.paths.sum_over_dims(other_dims)
        df = df.ensure_unit(metric, template.unit).filter(pl.col('Year') == year)
        if len(df) != 1:
            raise ValueError(f'Node {node.id} has no value for {year}')
        values[field] = float(df[metric][0])
    return values


@transaction.atomic
def write_defaults(
    fwc: FrameworkConfig,
    year: int,
    templates: dict[str, MeasureTemplate],
    values: dict[str, float],
    source: str,
) -> list[PrefillResult]:
    """Write each value as the city's default for `year`; city-entered values are left as they are."""
    results: list[PrefillResult] = []
    for field, template in templates.items():
        if template.dimensions.exists():
            raise ValueError(f'Form field {template.name!r} is split by dimensions; only single totals can be pre-filled')
        measure, _ = Measure.objects.get_or_create(framework_config=fwc, measure_template=template)
        dp, _ = MeasureDataPoint.objects.get_or_create(measure=measure, year=year)
        results.append(
            PrefillResult(
                field=field,
                template=template,
                year=year,
                default_value=values[field],
                previous_default=dp.default_value,
                city_value=dp.value,
            )
        )
        dp.default_value = values[field]
        dp.save(update_fields=['default_value'])

        note = f'{NOTE_PREFIX} ({source}, {year}).'
        kept = [line for line in measure.internal_notes.splitlines() if not line.startswith(NOTE_PREFIX)]
        measure.internal_notes = '\n'.join([*kept, note]).strip()
        measure.save(update_fields=['internal_notes'])
    fwc.notify_change(save=True)
    return results


def load_lacap_context(config_path: Path) -> Context:
    from nodes.instance_loader import InstanceLoader

    return InstanceLoader.from_yaml(config_path).context
