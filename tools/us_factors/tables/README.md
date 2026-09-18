# Generated factor tables

Empty until the build has been run somewhere with network access to epa.gov:

    python -m tools.us_factors.build_csv --all

The CSVs written here are the library itself and **are committed** — that is what
makes a new EPA release show up as a reviewable diff rather than an opaque
re-upload, and what lets the tables be checked before anyone has to trust a DVC
push.
