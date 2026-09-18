"""
Synthetic workbooks standing in for the published ones.

The values in these fixtures are **invented**, and deliberately so: they are
round numbers that could not be mistaken for a real emission factor. What is
being tested is that the parser finds the right cells and labels them correctly
-- the mapping from a spreadsheet's shape to a tidy row. Whether EPA's number is
53.06 or 53.11 is not something a fixture can establish, and pretending otherwise
by baking a half-remembered figure into a test would give false confidence in
exactly the place this package must not have any.

Each fixture reproduces the *shape* that makes real workbooks awkward: banner
rows above the header, a descriptive row between the header and the data, and
footnote rows below it.
"""
# ruff: noqa: TC003  # CLAUDE.md forbids `from __future__ import annotations`
# in new files, and without it the flake8-type-checking fixes are not available.



from pathlib import Path

import pytest
from openpyxl import Workbook


@pytest.fixture
def egrid_workbook(tmp_path: Path) -> Path:
    """Build an eGRID-shaped workbook: banner rows, a code header, a descriptive row, footnotes."""
    wb = Workbook()
    wb.remove(wb.active)

    sheet = wb.create_sheet('SRL23')
    sheet.append(['eGRID2023 Subregion File', None, None, None, None, None])
    sheet.append([None, None, None, None, None, None])
    sheet.append(['SEQSRL23', 'SUBRGN', 'SRNAME', 'SRCO2RTA', 'SRCH4RTA', 'SRN2ORTA', 'SRC2ERTA'])
    sheet.append([
        'Sequence', 'eGRID subregion acronym', 'eGRID subregion name',
        'CO2 total output rate', 'CH4 total output rate',
        'N2O total output rate', 'CO2e total output rate',
    ])
    sheet.append([1, 'AZNM', 'WECC Southwest', 700.0, 50.0, 6.0, 710.0])
    sheet.append([2, 'CAMX', 'WECC California', 500.0, 30.0, 4.0, 505.0])
    sheet.append([3, 'NEWE', 'NPCC New England', 600.0, 40.0, 5.0, 608.0])
    sheet.append([None, 'ZZZZ', 'Footnote row that is not a subregion', None, None, None, None])

    # A second sheet the parser must not pick up: same shape, different basis.
    other = wb.create_sheet('ST23')
    other.append(['STATE', 'STCO2RTA'])
    other.append(['AZ', 999.0])

    path = tmp_path / 'egrid2023.xlsx'
    wb.save(path)
    return path


@pytest.fixture
def epa_hub_workbook(tmp_path: Path) -> Path:
    """Build an Emission Factors Hub-shaped workbook: one table per sheet, banner above each."""
    wb = Workbook()
    wb.remove(wb.active)

    stationary = wb.create_sheet('Stationary Combustion')
    stationary.append(['Table 1 Stationary Combustion Emission Factors'])
    stationary.append([None])
    stationary.append([
        'Fuel type', 'kg CO2 per mmBtu', 'g CH4 per mmBtu', 'g N2O per mmBtu',
    ])
    stationary.append(['Natural Gas', 50.0, 1.0, 0.1])
    stationary.append(['Propane', 60.0, 3.0, 0.6])
    stationary.append([None, None, None, None])

    mobile = wb.create_sheet('Mobile Combustion CH4 and N2O')
    mobile.append(['Table 3 Mobile Combustion'])
    mobile.append(['Vehicle Type', 'g CH4 per mile', 'g N2O per mile'])
    mobile.append(['Passenger Car', 0.01, 0.02])
    mobile.append(['Light-Duty Truck', 0.03, 0.04])

    path = tmp_path / 'epa_hub.xlsx'
    wb.save(path)
    return path
