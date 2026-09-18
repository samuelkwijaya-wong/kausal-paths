"""
What emission factors the US city models already carry, and in what shape.

This is the structural half of the comparison the library exists to make
possible. It needs no data, no database and no network -- it reads ``configs/``
and reports every emission-factor node in the US instances, the dataset behind
it, its unit and its dimensions.

It answers the question that motivates the whole library: how much of this is the
same number written down more than once, and how far apart have the ways of
writing it drifted? The drift shows up in three places at once -- the same
physical quantity in different units, the same dimension under different names,
and the same public factor under a different per-city dataset id.

The value half -- do the numbers actually agree? -- lives in ``compare.py``,
which needs the city data exported and the library tables built.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / 'configs'

US_INSTANCES = (
    'sedona',
    'longmont',
    'longmont-2021',
    'minneapolis',
    'yolo',
    'king-county',
    'hollywood',
)
"""
The US city configs, as they exist today.

Deliberately an explicit list rather than a heuristic over ``theme_identifier``:
a model is in scope for this library because someone decided it is, not because
its theme happens to start with ``us-``.
"""

EMISSION_FACTOR_QUANTITY = 'emission_factor'
"""Matches ``EMISSION_FACTOR_QUANTITY`` in ``src/nodes/constants.py``."""


@dataclass(frozen=True)
class FactorNode:
    """One emission-factor node found in a city config."""

    instance: str
    node_id: str
    unit: str | None
    dimensions: tuple[str, ...]
    datasets: tuple[tuple[str, str | None], ...]
    """(dataset id, column) pairs the node reads."""

    @property
    def namespaces(self) -> tuple[str, ...]:
        return tuple(sorted({d.split('/')[0] for d, _ in self.datasets if '/' in d}))


@dataclass
class Survey:
    """Every emission-factor node across the surveyed instances."""

    nodes: list[FactorNode] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    """Instances named in ``US_INSTANCES`` whose config was not found."""

    def by_instance(self) -> dict[str, list[FactorNode]]:
        out: dict[str, list[FactorNode]] = defaultdict(list)
        for node in self.nodes:
            out[node.instance].append(node)
        return dict(out)

    def shared_namespaces(self) -> set[str]:
        """Dataset namespaces used by more than one instance -- i.e. already shared."""
        holders: dict[str, set[str]] = defaultdict(set)
        for node in self.nodes:
            for ns in node.namespaces:
                holders[ns].add(node.instance)
        return {ns for ns, who in holders.items() if len(who) > 1}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]  # type: ignore[union-attr]


def _node_datasets(node: dict) -> tuple[tuple[str, str | None], ...]:
    out: list[tuple[str, str | None]] = []
    for entry in node.get('input_datasets') or []:
        if isinstance(entry, str):
            out.append((entry, None))
        elif isinstance(entry, dict) and 'id' in entry:
            out.append((str(entry['id']), entry.get('column')))
    return tuple(out)


def survey_config(path: Path) -> list[FactorNode]:
    """Return the emission-factor nodes declared in one instance config."""
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        return []
    instance = str(data.get('id') or path.stem)

    found: list[FactorNode] = []
    for node in data.get('nodes') or []:
        if not isinstance(node, dict):
            continue
        if node.get('quantity') != EMISSION_FACTOR_QUANTITY:
            continue
        found.append(
            FactorNode(
                instance=instance,
                node_id=str(node.get('id', '<unnamed>')),
                unit=str(node['unit']) if node.get('unit') is not None else None,
                dimensions=tuple(_as_list(node.get('input_dimensions'))),
                datasets=_node_datasets(node),
            )
        )
    return found


def run(instances: tuple[str, ...] = US_INSTANCES, config_dir: Path = CONFIG_DIR) -> Survey:
    """Survey every named instance whose config exists."""
    result = Survey()
    for name in instances:
        path = config_dir / f'{name}.yaml'
        if not path.exists():
            result.missing.append(name)
            continue
        result.nodes.extend(survey_config(path))
    return result


def _normalise_unit(unit: str | None) -> str:
    """
    Fold a unit to its physical shape, so that different spellings group together.

    ``lb*CO2e/MWh``, ``lbs/MWh`` and ``t_co2e/MWh`` all measure mass per unit of
    electricity; the gas marker and the pluralisation are noise for the purpose
    of noticing that three cities wrote the same quantity three ways.
    """
    if unit is None:
        return '<none>'
    text = unit.strip().strip("'\"").lower()
    text = re.sub(r'[_*]?co2e?\b', '', text)
    text = text.replace('lbs', 'lb').replace('*', '').replace('__', '_')
    return re.sub(r'_+', '', text).strip('/_ ') or '<none>'


def _section_nodes(survey: Survey) -> list[str]:
    """Every factor node, grouped by the instance that carries it."""
    lines = ['US emission-factor nodes by instance', '=' * 72]
    by_instance = survey.by_instance()
    for instance in sorted(by_instance):
        nodes = by_instance[instance]
        lines.append(f'\n{instance}  ({len(nodes)} factor nodes)')
        lines.extend(
            f'  {node.node_id:44} {node.unit or "-":18} '
            f'{", ".join(f"{d}[{c}]" if c else d for d, c in node.datasets) or "-"}'
            for node in sorted(nodes, key=lambda n: n.node_id)
        )
    return lines


def _section_unit_spellings(survey: Survey) -> list[str]:
    """Physical quantities that more than one city spells differently."""
    lines = ['', 'Same quantity, different spellings', '=' * 72]
    grouped: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for node in survey.nodes:
        grouped[_normalise_unit(node.unit)].add((node.instance, node.unit or '-'))
    for shape, entries in sorted(grouped.items()):
        if len({unit for _, unit in entries}) < 2:
            continue
        lines.append(f'\n  {shape}:')
        lines.extend(f'    {unit:20} {instance}' for instance, unit in sorted(entries))
    return lines


def _section_dimensions(survey: Survey) -> list[str]:
    """Every dimension name in use, and who uses it."""
    lines = ['', 'Dimension names in use', '=' * 72]
    dims: dict[str, set[str]] = defaultdict(set)
    for node in survey.nodes:
        for dim in node.dimensions:
            dims[dim].add(node.instance)
    lines.extend(f'  {dim:24} {", ".join(sorted(who))}' for dim, who in sorted(dims.items()))
    return lines


def _section_summary(survey: Survey) -> list[str]:
    """Return the counts that say how much duplication there is."""
    namespaces = {ns for node in survey.nodes for ns in node.namespaces}
    shared = survey.shared_namespaces()
    lines = [
        '',
        'Summary',
        '=' * 72,
        f'  instances surveyed     {len(survey.by_instance())}',
        f'  emission-factor nodes  {len(survey.nodes)}',
        f'  dataset namespaces     {len(namespaces)}  ({", ".join(sorted(namespaces))})',
        f'  shared across cities   {", ".join(sorted(shared)) if shared else "none"}',
    ]
    if survey.missing:
        lines.append(f'  configs not found      {", ".join(survey.missing)}')
    return lines


def format_report(survey: Survey) -> str:
    """Render the survey as a plain-text report."""
    return '\n'.join([
        *_section_nodes(survey),
        *_section_unit_spellings(survey),
        *_section_dimensions(survey),
        *_section_summary(survey),
    ])


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog='python -m tools.us_factors.survey',
        description='Report the emission-factor nodes carried by the US city configs.',
    )
    parser.add_argument(
        'instances', nargs='*', default=None,
        help=f'Instances to survey (default: {" ".join(US_INSTANCES)}).',
    )
    parser.add_argument('--config-dir', type=Path, default=CONFIG_DIR)
    args = parser.parse_args(argv)

    result = run(tuple(args.instances) if args.instances else US_INSTANCES, args.config_dir)
    print(format_report(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
