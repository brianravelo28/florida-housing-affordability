"""
Checks the conversion of the early home values to 2024 dollars, the one input that does not come from the Census Bureau.

The Census Bureau did not inflation-adjust home value before its 2018-2022 release, so the 2010-2014 and 2015-2019 values are
converted with the average-year factor (acs_config.home_value_factor). This script writes how far that differs from
  - converting with the final-year factor (with the Census Bureau's published factor and with the CPI-U ratio), and
  - a second method: the Census Bureau's single-year Florida medians (data/home_value_1year_medians.csv), each converted with its
    own year's CPI-U and averaged.
Output: data/processed/home_value_conversion_check.csv, the only source for the figures the Methodology quotes.

Run: python src/home_value_conversion_check.py           (reads the stored medians; no network)
     python src/home_value_conversion_check.py --fetch   (re-pulls the single-year medians first; needs CENSUS_API_KEY)
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd

import acs_config as cfg

EARLY_PERIODS = {'2010-2014': 2014, '2015-2019': 2019}
LATEST_PERIOD = cfg.LATEST_PERIOD
ONE_YEAR_URL = 'https://api.census.gov/data/{year}/acs/acs1'


def fetch_one_year_medians(key, years=range(2010, 2020), session=None):
    """The single-year (ACS 1-year) Florida median home value, nominal dollars, for each year"""
    import requests
    import fetch_acs
    session = session or requests
    rows, retrieved = [], datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    for year in years:
        url = ONE_YEAR_URL.format(year=year)
        response = session.get(url, params={'get': 'B25077_001E', 'for': f'state:{cfg.STATE_FIPS}', 'key': key}, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"ACS 1-year request failed for {year}: {fetch_acs.scrub(response.text[:150], key)}")
        rows.append({'year': year, 'median_home_value': int(response.json()[1][0]), 'endpoint': url,
                     'retrieved_at_utc': retrieved})
    return pd.DataFrame(rows)


def conversion_check(state, one_year, cpi=None):
    """
    One row per early period. `state` is data/processed/state.csv, `one_year` the stored single-year medians.
    Factors and growth are for converting to 2024 dollars and comparing with the 2020-2024 median (already in 2024 dollars).
    """
    cpi = cpi or cfg.CPI_U_ANNUAL_AVERAGE
    s = state.set_index('period')
    latest = s.loc[LATEST_PERIOD, 'home_value']
    yearly = one_year.set_index('year')['median_home_value']
    rows = []
    for period, year in EARLY_PERIODS.items():
        published = s.loc[period, 'home_value_as_published']
        years = range(year - 4, year + 1)
        factor_census = cfg.DOLLAR_FACTORS_TO_2024[year]
        factor_cpi = cpi[cfg.DOLLAR_YEAR] / cpi[year]
        factor_average = cpi[cfg.DOLLAR_YEAR] / (sum(cpi[y] for y in years) / 5)
        used = published * factor_average
        final_census, final_cpi = published * factor_census, published * factor_cpi
        yearly_method = sum(yearly[y] * cpi[cfg.DOLLAR_YEAR] / cpi[y] for y in years) / 5
        growth = lambda converted: (latest / converted - 1) * 100
        rows.append({
            'period': period, 'published_median': published,
            'factor_average_year': factor_average, 'factor_final_year_census': factor_census, 'factor_final_year_cpi': factor_cpi,
            'converted_average_year': used, 'converted_final_year_census': final_census, 'converted_final_year_cpi': final_cpi,
            'converted_yearly_medians': yearly_method,
            'cpi_vs_census_factor_pct': (factor_cpi / factor_census - 1) * 100,
            'understatement_pct_census': (used / final_census - 1) * 100,
            'understatement_pct_cpi': (used / final_cpi - 1) * 100,
            'growth_pct_average_year': growth(used), 'growth_pct_final_year_census': growth(final_census),
            'growth_pct_final_year_cpi': growth(final_cpi), 'growth_pct_yearly_medians': growth(yearly_method),
            'growth_overstatement_points_census': growth(final_census) - growth(used),
            'growth_overstatement_points_cpi': growth(final_cpi) - growth(used),
            'method_gap_pct': (yearly_method / used - 1) * 100,
            'method_gap_growth_points': growth(yearly_method) - growth(used),
        })
    return pd.DataFrame(rows)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--fetch' in argv:
        import fetch_acs
        medians = fetch_one_year_medians(fetch_acs.load_key())
        medians.to_csv(cfg.ONE_YEAR_MEDIANS_PATH, index=False)
        print(f"Wrote {cfg.ONE_YEAR_MEDIANS_PATH}")
    state = pd.read_csv(os.path.join(cfg.PROCESSED_DIR, 'state.csv'))
    one_year = pd.read_csv(cfg.ONE_YEAR_MEDIANS_PATH)
    result = conversion_check(state, one_year)
    result.to_csv(cfg.CONVERSION_CHECK_PATH, index=False, float_format='%.10g')
    print(result.T.to_string(header=False))
    print(f"Wrote {cfg.CONVERSION_CHECK_PATH}")


if __name__ == '__main__':
    main()
