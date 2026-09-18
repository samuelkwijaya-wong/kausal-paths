"""
Fetching and provenance.

The rule under test throughout: a factor is only publishable if the file it came
from is identified. So every path that yields a file must also yield a record of
which file it was, and every path that cannot must raise rather than improvise.
"""

import json

import pytest

from tools.us_factors import provenance
from tools.us_factors.provenance import (
    ManualSourceSpec,
    SourceSpec,
    SourceUnavailableError,
    fetch,
)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Redirect the package cache at a temporary directory."""
    monkeypatch.setattr(provenance, 'CACHE_DIR', tmp_path)
    return tmp_path


def make_spec(**kwargs) -> SourceSpec:
    defaults = {
        'key': 'demo',
        'url': 'https://example.invalid/demo.xlsx',
        'authority': 'US EPA',
        'edition': 'Demo 2025',
        'citation': 'Demo citation.',
    }
    defaults.update(kwargs)
    return SourceSpec(**defaults)


def test_source_label_is_what_lands_in_the_csv() -> None:
    assert make_spec().source_label() == 'US EPA Demo 2025'


def test_offline_refuses_when_nothing_is_cached(cache) -> None:
    with pytest.raises(SourceUnavailableError, match='not cached'):
        fetch(make_spec(), offline=True)


def test_offline_error_names_the_url_to_fetch(cache) -> None:
    """The error has to be actionable: it is read by whoever must go and get the file."""
    with pytest.raises(SourceUnavailableError) as exc:
        fetch(make_spec(), offline=True)

    assert 'https://example.invalid/demo.xlsx' in str(exc.value)
    assert str(cache / 'demo.xlsx') in str(exc.value)


def test_offline_adopts_a_hand_placed_file(cache) -> None:
    """
    Adopt a file placed in the cache by hand.

    Such a file has no provenance sidecar -- that is the documented workflow
    where the network blocks the publisher, so it must be accepted and recorded
    rather than rejected for missing a record it could not have had.
    """
    spec = make_spec()
    spec.cache_path.write_bytes(b'workbook bytes')

    retrieval = fetch(spec, offline=True)

    assert retrieval.path == spec.cache_path
    assert retrieval.size_bytes == len(b'workbook bytes')
    assert spec.record_path.exists()

    record = json.loads(spec.record_path.read_text())
    assert record['edition'] == 'Demo 2025'
    assert record['sha256'] == retrieval.sha256


def test_a_cached_file_is_reused_without_network(cache) -> None:
    spec = make_spec()
    spec.cache_path.write_bytes(b'x')
    first = fetch(spec, offline=True)

    second = fetch(spec, offline=True)

    assert second.sha256 == first.sha256
    assert second.retrieved_at == first.retrieved_at  # read back from the record


def test_manual_source_never_reaches_the_network(cache) -> None:
    """Cambium cannot be scripted, so its absence is an instruction, not a network fault."""
    spec = ManualSourceSpec(
        key='manual',
        url='https://scenarioviewer.invalid/',
        authority='NREL',
        edition='Cambium 2023',
        citation='Citation.',
        suffix='.csv',
        instructions='Download it from the viewer and save it here.',
    )

    with pytest.raises(SourceUnavailableError) as exc:
        fetch(spec, offline=False)

    assert 'placed by hand' in str(exc.value)
    assert 'Download it from the viewer' in str(exc.value)


def test_manual_source_must_carry_instructions() -> None:
    """A manual source with no instructions is unusable by whoever hits it."""
    with pytest.raises(ValueError, match='must say how to obtain'):
        ManualSourceSpec(
            key='manual',
            url='https://example.invalid/',
            authority='NREL',
            edition='X',
            citation='Y',
        )
