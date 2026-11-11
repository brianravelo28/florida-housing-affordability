"""
Settings for the Florida housing affordability pipeline: which ACS releases and tables to pull,
how to read the Census API's special values, and the inflation factors used to put dollars
from different periods in the same year's terms.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, 'data', 'raw')              # API responses (rebuilt by the pipeline, not committed)
PROCESSED_DIR = os.path.join(ROOT, 'data', 'processed')  # cleaned tables and simplified boundaries (committed)
MANIFEST_PATH = os.path.join(ROOT, 'data', 'manifest.json')

STATE_FIPS = '12'  # Florida
API_BASE = 'https://api.census.gov/data/{year}/acs/acs5'

# ACS 5-year period -> the API's year (the last year of the period). Census advises comparing only
# non-overlapping periods, so these three are the timeline.
RELEASES = {'2010-2014': 2014, '2015-2019': 2019, '2020-2024': 2024}
LATEST_PERIOD = '2020-2024'
DOLLAR_YEAR = 2024  # every dollar figure in the processed tables is expressed in 2024 dollars

# R-CPI-U-RS factors published by the Census Bureau for comparing ACS 5-year periods (ACS dollar values
# are adjusted to the final year of each period). Chained to 2024 dollars:
#   2019 -> 2024: 1.23070782  (2024 annual average 462.5 / 2019 annual average 375.8; Census, "Comparing 2024 ACS data")
#   2014 -> 2019: 1.08096469  (Census, "Comparing 2019 ACS data")
FACTOR_2019_TO_2024 = 1.23070782
FACTOR_2014_TO_2019 = 1.08096469
DOLLAR_FACTORS_TO_2024 = {
    2014: FACTOR_2014_TO_2019 * FACTOR_2019_TO_2024,
    2019: FACTOR_2019_TO_2024,
    2024: 1.0,
}

# Releases whose home values the Census Bureau did NOT adjust to final-year dollars (it started with the
# 2018-2022 release). Income and rent are adjusted in every release.
HOME_VALUE_UNADJUSTED_API_YEARS = (2014, 2019)

# Those home values are the raw medians of values reported across the five survey years, so converting them
# with the final-year factor would treat them as final-year dollars and understate them by about 3-4%. Instead
# they are converted with the factor for the average year of the period: 2024 CPI-U / mean CPI-U of the period's
# five years. CPI-U annual averages (U.S. city average, all items, 1982-84=100) from the Bureau of Labor
# Statistics API, series CUUR0000SA0, retrieved 2026-11-04. They reproduce the factors Census publishes
# (R-CPI-U-RS) within 0.3%.
CPI_U_ANNUAL_AVERAGE = {
    2010: 218.056, 2011: 224.939, 2012: 229.594, 2013: 232.957, 2014: 236.736,
    2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657,
    2020: 258.811, 2021: 270.970, 2022: 292.655, 2023: 304.702, 2024: 313.689,
}


def home_value_factor(api_year):
    """Factor converting a release's published median home value to 2024 dollars"""
    if api_year not in HOME_VALUE_UNADJUSTED_API_YEARS:
        return DOLLAR_FACTORS_TO_2024[api_year]  # Census already adjusted it to the final year
    period_years = range(api_year - 4, api_year + 1)
    average = sum(CPI_U_ANNUAL_AVERAGE[y] for y in period_years) / 5
    return CPI_U_ANNUAL_AVERAGE[DOLLAR_YEAR] / average


# ---- Tables ----------------------------------------------------------------------------------------
# Medians: each has an estimate (E) and a margin of error (M, 90% confidence).
MEDIANS = {
    'home_value': 'B25077_001',   # median value (dollars), owner-occupied units
    'rent': 'B25064_001',         # median gross rent (dollars)
    'income': 'B19013_001',       # median household income, past 12 months
}

# Rent as a percent of household income (B25070): total, the four 30%+ bins, and "not computed"
RENT_BURDEN_TOTAL = 'B25070_001'
RENT_BURDEN_30PLUS = ['B25070_007', 'B25070_008', 'B25070_009', 'B25070_010']
RENT_BURDEN_NOT_COMPUTED = 'B25070_011'

# Counts carried through for context and for the county-sums-to-state check
COUNTS = {
    'housing_units': 'B25001_001',
    'households': 'B25003_001',
    'owner_households': 'B25003_002',
    'renter_households': 'B25003_003',
}


def _estimate_and_margin(base):
    return [base + 'E', base + 'M']


ALL_BASES = (list(MEDIANS.values()) + [RENT_BURDEN_TOTAL] + RENT_BURDEN_30PLUS + [RENT_BURDEN_NOT_COMPUTED]
             + list(COUNTS.values()))
VARIABLES = [v for base in ALL_BASES for v in _estimate_and_margin(base)]

# ---- Special values and reliability ---------------------------------------------------------------
# The API returns large negative numbers where there is no usable value. Seen in the 2024 tract data:
#   -666666666  estimate not available (too few sample cases)
#   -222222222  margin of error not available (accompanies the above)
#   -333333333  margin of error not applicable because the median is at the top (or bottom) of the open-ended range;
#               the estimate is then the cap itself (e.g. 2,000,001 for home value)
# Any negative value below -200,000,000 is treated as special.
SPECIAL_VALUE_CEILING = -200_000_000
TOP_CODED_MARGIN = -333_333_333

# Reliability: the Census Bureau recommends the coefficient of variation, CV = (margin of error / 1.645) / estimate.
# The three bands are an Esri guideline that the Census Bureau's handbook for rural data users quotes (chapter 4,
# footnote 29): a convention, not a Census Bureau standard.
Z_90 = 1.645
CV_HIGH_BELOW = 12.0   # CV under 12%: high reliability
CV_LOW_ABOVE = 40.0    # CV over 40%: low reliability (grayed out on the map); 12%-40% is moderate
