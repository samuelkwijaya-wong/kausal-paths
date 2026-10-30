"""
Check the adaptation-demo instance against the test cases in its build brief.

The instance's data lives in `configs/adaptation-demo/datasets.csv` in the wide upload
format. Instead of reading it from the dataset repo, the test runs it through the same
read-side pipeline as `tools/upload_new_dataset.py` and hands the frames to the context,
so the CSV is checked to be uploadable as well.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import dvc_pandas
import polars as pl
import pytest

from nodes.actions.action import ActionNode
from nodes.instance_loader import InstanceLoader
from tools.upload_new_dataset import build_dvc_frame, load_data, split_by_dataset, to_snake_case

if TYPE_CHECKING:
    from nodes.context import Context

pytestmark = pytest.mark.django_db

CONFIGS = Path(__file__).parents[3] / 'configs'
TARGET_YEAR = 2030
ACTIONS = ('cooling_centres', 'checkin_service', 'street_trees', 'flood_barrier')


@pytest.fixture
def demo_context() -> Context:
    loader = InstanceLoader.from_yaml(CONFIGS / 'adaptation-demo.yaml')
    context = loader.context
    raw = load_data(str(CONFIGS / 'adaptation-demo' / 'datasets.csv'), ',', 'utf-8')
    for name, rows in split_by_dataset(raw).items():
        frame, units, _metrics, _description = build_dvc_frame(rows, 'en', context, verbose=False)
        # Per-row sources go to the dataset's metadata on upload, not into the frame.
        frame = frame.drop('source')
        ds_id = 'adaptation_demo/%s' % to_snake_case(name)
        index_columns = [col for col in frame.columns if col not in units]
        meta = dvc_pandas.DatasetMeta(identifier=ds_id, units=units, index_columns=index_columns)
        context.dvc_datasets[ds_id] = dvc_pandas.Dataset(frame, meta)
    return context


def _people_at_high_risk(context: Context, enabled: set[str]) -> tuple[float, float, float]:
    """Return people at high risk from heat, from flooding, and from either, in the target year."""
    for action_id in ACTIONS:
        action = context.get_node(action_id)
        assert isinstance(action, ActionNode)
        action.enabled_param.set(action_id in enabled)
    with context.run():
        by_hazard = context.get_node('people_at_high_risk_by_hazard').get_output_pl()
        either = context.get_node('people_in_high_risk_areas').get_output_pl()
    by_hazard = by_hazard.filter(pl.col('Year') == TARGET_YEAR)
    values = dict(zip(by_hazard['climate_hazard'], by_hazard['Value'], strict=True))
    total = either.filter(pl.col('Year') == TARGET_YEAR)['Value'].item()
    return values['heat'], values['flood'], total


@pytest.mark.parametrize(
    ('enabled', 'hazard', 'expected'),
    [
        ((), 'heat', 27_400),
        (('cooling_centres',), 'heat', 18_800),
        (('checkin_service',), 'heat', 15_200),
        # 16,000 protected, not the 20,800 from adding the two: the larger reduction counts.
        (('cooling_centres', 'checkin_service'), 'heat', 11_400),
        (('street_trees',), 'heat', 19_300),
        ((), 'flood', 12_100),
        (('flood_barrier',), 'flood', 4_200),
        ((), 'either', 31_600),
        (ACTIONS, 'either', 15_600),
    ],
)
def test_brief_test_cases(demo_context: Context, enabled: tuple[str, ...], hazard: str, expected: int) -> None:
    heat, flood, either = _people_at_high_risk(demo_context, set(enabled))
    assert {'heat': heat, 'flood': flood, 'either': either}[hazard] == pytest.approx(expected)


def test_cut_one_action_does_not_add_up(demo_context: Context) -> None:
    """Cutting actions one by one loses more people than the whole plan protects, as overlaps count twice."""
    _, _, nothing = _people_at_high_risk(demo_context, set())
    _, _, full = _people_at_high_risk(demo_context, set(ACTIONS))
    losses = {a: _people_at_high_risk(demo_context, set(ACTIONS) - {a})[2] - full for a in ACTIONS}
    assert all(loss >= 0 for loss in losses.values())
    assert sum(losses.values()) != pytest.approx(nothing - full)


def test_plan_cost(demo_context: Context) -> None:
    _people_at_high_risk(demo_context, set(ACTIONS))
    with demo_context.run():
        costs = demo_context.get_node('adaptation_plan_costs').get_output_pl()
    assert costs['Value'].sum() == pytest.approx(7.3)
