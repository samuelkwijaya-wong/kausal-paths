"""
Pre-fill a city's NetZeroCities form from its Irish LACAP inventory.

The LACAP model (an instance config that includes ``configs/modules/ie/lacap.yaml``) computes
suggested values for building heat energy use, electricity consumption and emissions from other
sectors. This command writes them as the city's default values for one year, by default the city's
reference year. Values the city has entered are not changed and keep taking precedence.

Name the form fields by measure-template UUID; any of the three can be left out. Nothing is written
without ``--apply``.

``refresh_measure_defaults`` resets default values of templates that have template defaults, so run
this command again after it.

Example::

    python manage.py prefill_nzc_from_lacap --instance dublin-nzc \
        --lacap-config configs/ie-lacap-dublin.yaml \
        --building-heat <uuid> --electricity <uuid> --other-sectors <uuid> --apply
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from frameworks.lacap_prefill import SUGGESTION_NODES, compute_suggestions, load_lacap_context, write_defaults
from frameworks.models import FrameworkConfig, MeasureTemplate

if TYPE_CHECKING:
    from django.core.management.base import CommandParser


class Command(BaseCommand):
    help = "Pre-fill a city's NetZeroCities form with default values from its LACAP inventory"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--instance', required=True, help='Instance identifier of the NetZeroCities city')
        parser.add_argument('--lacap-config', required=True, help="YAML config of the city's LACAP model")
        parser.add_argument('--year', type=int, help="Year to pre-fill (default: the city's reference year)")
        for field in SUGGESTION_NODES:
            parser.add_argument(f'--{field.replace("_", "-")}', dest=field, metavar='UUID', help='Form field UUID')
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run)')

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            fwc = FrameworkConfig.objects.get(instance_config__identifier=options['instance'])
        except FrameworkConfig.DoesNotExist as err:
            raise CommandError(f'No framework config for instance {options["instance"]}') from err

        templates: dict[str, MeasureTemplate] = {}
        for field in SUGGESTION_NODES:
            uuid = options[field]
            if not uuid:
                continue
            try:
                templates[field] = MeasureTemplate.objects.get(uuid=uuid, section__framework=fwc.framework)
            except MeasureTemplate.DoesNotExist as err:
                raise CommandError(f'No form field {uuid} in framework {fwc.framework.identifier}') from err
        if not templates:
            raise CommandError('Name at least one form field: ' + ', '.join(f'--{f.replace("_", "-")}' for f in SUGGESTION_NODES))

        year = options['year'] or fwc.reference_year
        config_path = Path(options['lacap_config']).resolve()
        context = load_lacap_context(config_path)
        values = compute_suggestions(context, year, templates)

        with transaction.atomic():
            results = write_defaults(fwc, year, templates, values, source=f'{context.instance.id} ({config_path.name})')
            for r in results:
                previous = 'none' if r.previous_default is None else f'{r.previous_default:.6g}'
                city = 'no city value' if r.city_value is None else f'city value {r.city_value:.6g} kept, it takes precedence'
                self.stdout.write(
                    f'  {r.template.name} [{r.template.unit}] {r.year}: default {previous} -> {r.default_value:.6g} ({city})'
                )
            if not options['apply']:
                transaction.set_rollback(True)

        if options['apply']:
            self.stdout.write(self.style.SUCCESS(f'Pre-filled {len(results)} fields for {options["instance"]}'))
        else:
            self.stdout.write('Dry run: rolled back. Re-run with --apply to write.')
