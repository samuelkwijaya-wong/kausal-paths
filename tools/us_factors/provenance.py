"""
Downloading upstream workbooks, and recording where each one came from.

A factor is only as trustworthy as the record of where it came from, so nothing
here fetches a file without also writing down the URL it came from, when it was
retrieved and the checksum of what arrived. That record is what later becomes the
``Source`` column of the published CSV, and from there a ``DataSource`` row with
``url`` / ``authority`` / ``edition`` fields.

The cache is deliberately content-addressed by declared edition rather than by
URL hash: re-running the build must not silently pick up a different vintage of
eGRID because EPA moved a file.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).parent / 'cache'

DOWNLOAD_TIMEOUT = (10, 120)
"""Connect and read timeouts. The eGRID workbook is tens of megabytes."""


class SourceUnavailableError(RuntimeError):
    """
    A source could not be downloaded and is not in the cache.

    Raised rather than falling back to any built-in value. There is no
    circumstance in which this package should emit an emission factor it did not
    read out of a published file -- a plausible-looking wrong factor is worse
    than a missing one, because it computes.
    """


@dataclass(frozen=True)
class SourceSpec:
    """One downloadable file from an upstream publisher."""

    key: str
    """Short identifier, also the cache filename stem (e.g. ``egrid2023``)."""

    url: str
    authority: str
    """The publishing body, e.g. ``US EPA``. Becomes ``DataSource.authority``."""

    edition: str
    """The release as the publisher names it, e.g. ``eGRID2023``. Becomes ``DataSource.edition``."""

    citation: str
    """How the publisher asks to be cited, or a plain reference where they do not."""

    suffix: str = '.xlsx'

    @property
    def cache_path(self) -> Path:
        return CACHE_DIR / f'{self.key}{self.suffix}'

    @property
    def record_path(self) -> Path:
        return CACHE_DIR / f'{self.key}.provenance.json'

    def source_label(self) -> str:
        """Return the one-line provenance string that rides in the CSV's ``Source`` column."""
        return f'{self.authority} {self.edition}'


@dataclass(frozen=True)
class ManualSourceSpec(SourceSpec):
    """
    A source that cannot be fetched programmatically and must be placed by hand.

    NREL's Cambium projections sit behind a viewer that requires accepting terms
    before download, so there is no URL a script can GET. Rather than pretend
    otherwise with a fetcher that will always fail, such a source declares itself
    manual: ``fetch`` never reaches the network for it, and the error when the
    file is absent explains where to get it instead of reporting a network fault.
    """

    instructions: str = ''

    def __post_init__(self) -> None:
        if not self.instructions:
            raise ValueError(f'Manual source {self.key} must say how to obtain the file.')


@dataclass
class Retrieval:
    """What actually arrived, recorded beside the cached file."""

    spec: SourceSpec
    sha256: str
    retrieved_at: str
    size_bytes: int
    path: Path = field(repr=False)

    def as_record(self) -> dict[str, object]:
        return {
            'key': self.spec.key,
            'url': self.spec.url,
            'authority': self.spec.authority,
            'edition': self.spec.edition,
            'citation': self.spec.citation,
            'sha256': self.sha256,
            'retrieved_at': self.retrieved_at,
            'size_bytes': self.size_bytes,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_record(spec: SourceSpec) -> Retrieval | None:
    if not spec.cache_path.exists() or not spec.record_path.exists():
        return None
    record = json.loads(spec.record_path.read_text())
    return Retrieval(
        spec=spec,
        sha256=record['sha256'],
        retrieved_at=record['retrieved_at'],
        size_bytes=record['size_bytes'],
        path=spec.cache_path,
    )


def _adopt(spec: SourceSpec) -> Retrieval:
    """Record provenance for a file already sitting in the cache, placed by hand."""
    retrieval = Retrieval(
        spec=spec,
        sha256=_sha256(spec.cache_path),
        retrieved_at=datetime.now(UTC).isoformat(timespec='seconds'),
        size_bytes=spec.cache_path.stat().st_size,
        path=spec.cache_path,
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    spec.record_path.write_text(json.dumps(retrieval.as_record(), indent=2) + '\n')
    return retrieval


def fetch(spec: SourceSpec, *, refresh: bool = False, offline: bool = False) -> Retrieval:
    """
    Return the local copy of ``spec``, downloading it if needed.

    ``offline`` refuses to reach the network at all, which is how the build runs
    in an environment whose egress policy blocks the publishers. It uses the
    cache when one exists and raises otherwise -- it never substitutes a value.
    """
    cached = None if refresh else _load_record(spec)
    if cached is not None:
        return cached

    if isinstance(spec, ManualSourceSpec):
        # A manual source may have been dropped in without a provenance sidecar,
        # which is the normal way it arrives. Adopt the file and record it.
        if spec.cache_path.exists():
            return _adopt(spec)
        raise SourceUnavailableError(
            f'{spec.key} must be placed by hand and is not present.\n'
            f'  Expected file: {spec.cache_path}\n'
            f'  {spec.instructions}'
        )

    if offline:
        # A file downloaded by hand arrives without a provenance sidecar, which is
        # the documented way to work in an environment that blocks the publishers.
        # Adopt it and write the record, rather than insisting on a sidecar the
        # person had no way to produce.
        if spec.cache_path.exists():
            return _adopt(spec)
        raise SourceUnavailableError(
            f'{spec.key} is not cached and offline mode forbids downloading it.\n'
            f'  Expected file: {spec.cache_path}\n'
            f'  Download from: {spec.url}\n'
            'Fetch it on a machine with network access and copy it into the cache directory.'
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = spec.cache_path.with_suffix(spec.suffix + '.part')
    try:
        with requests.get(spec.url, timeout=DOWNLOAD_TIMEOUT, stream=True) as response:
            response.raise_for_status()
            with tmp_path.open('wb') as f:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except requests.RequestException as exc:
        tmp_path.unlink(missing_ok=True)
        raise SourceUnavailableError(
            f'Could not download {spec.key} from {spec.url}: {exc}\n'
            'If this environment blocks the publisher, run with --offline after placing '
            f'the file at {spec.cache_path}.'
        ) from exc

    tmp_path.replace(spec.cache_path)
    retrieval = Retrieval(
        spec=spec,
        sha256=_sha256(spec.cache_path),
        retrieved_at=datetime.now(UTC).isoformat(timespec='seconds'),
        size_bytes=spec.cache_path.stat().st_size,
        path=spec.cache_path,
    )
    spec.record_path.write_text(json.dumps(retrieval.as_record(), indent=2) + '\n')
    return retrieval
