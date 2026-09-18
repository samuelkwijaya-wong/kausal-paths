"""
A library of US emission factors, built from public federal sources.

Paths has a shared factor library for exactly one country: Germany, as the
``de/`` dataset namespace declared in ``configs/modules/bisko/model.yaml``. Every
US city instead carries its own hand-copied transcription of the same public EPA
numbers -- ``sedona/grid_emission_factors``, ``longmont/emission_factor_natural_gas``,
``minneapolis``'s four factor tables, and so on. They are the same numbers, copied
from consultant workbooks into six separate places, with no record of which eGRID
release each one came from.

This package builds the US equivalent of ``de/``: a ``us/`` namespace of factor
tables derived from the published sources, with the provenance of every value
recorded alongside it.

Layout
------
``sources/``    one module per upstream publisher; each downloads and parses.
``tidy.py``     the shared row contract and the wide-CSV writer.
``regions.py``  eGRID subregion codes.
``build_csv.py``  the entry point that writes ``tables/``.
``tables/``     the generated CSVs -- the library itself, committed.
``cache/``      downloaded workbooks, gitignored.

Run it as a module, following the convention of the rest of ``tools/``::

    python -m tools.us_factors.build_csv --help
"""
