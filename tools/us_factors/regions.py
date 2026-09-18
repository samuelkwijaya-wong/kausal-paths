"""
eGRID subregion codes.

These are the keys a US city uses to pick its own grid factor out of the shared
table -- the ``egrid_subregion`` dimension. They are structural metadata rather
than measurements: the list changes only when EPA redraws the subregions, which
is rare and announced.

The list is used to *validate* what the parser read, not to supply it. If EPA
adds or renames a subregion the parser reports the unknown code rather than
dropping the row, so a boundary change shows up as a loud failure instead of a
city silently losing its factor.
"""

EGRID_SUBREGIONS: dict[str, str] = {
    'AKGD': 'ASCC Alaska Grid',
    'AKMS': 'ASCC Miscellaneous',
    'AZNM': 'WECC Southwest',
    'CAMX': 'WECC California',
    'ERCT': 'ERCOT All',
    'FRCC': 'FRCC All',
    'HIMS': 'HICC Miscellaneous',
    'HIOA': 'HICC Oahu',
    'MROE': 'MRO East',
    'MROW': 'MRO West',
    'NEWE': 'NPCC New England',
    'NWPP': 'WECC Northwest',
    'NYCW': 'NPCC NYC/Westchester',
    'NYLI': 'NPCC Long Island',
    'NYUP': 'NPCC Upstate NY',
    'PRMS': 'Puerto Rico Miscellaneous',
    'RFCE': 'RFC East',
    'RFCM': 'RFC Michigan',
    'RFCW': 'RFC West',
    'RMPA': 'WECC Rockies',
    'SPNO': 'SPP North',
    'SPSO': 'SPP South',
    'SRMV': 'SERC Mississippi Valley',
    'SRMW': 'SERC Midwest',
    'SRSO': 'SERC South',
    'SRTV': 'SERC Tennessee Valley',
    'SRVC': 'SERC Virginia/Carolina',
}
"""
Subregion acronym -> name, as EPA publishes them.

Verify against the ``SUBRGN`` / ``SRNAME`` columns of the first real workbook the
build reads; ``build_csv.py --inspect`` prints what the file actually contains.
"""


def is_known_subregion(code: str) -> bool:
    return code.upper() in EGRID_SUBREGIONS
