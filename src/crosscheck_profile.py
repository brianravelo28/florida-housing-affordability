"""
Cross-checks three counties against the Census Bureau's Data Profile tables.

The pipeline reads the detailed tables (B25077, B25064, B19013). The Data Profile tables (DP04, DP03) publish the same medians
through a separate path in the same API, so agreement is evidence that the pulls and the parsing are right. Compared: the
as-published values (before any dollar conversion) for Miami-Dade, Monroe and Alachua, home value, rent and income, in the
2015-2019 and 2020-2024 releases. Output: data/processed/profile_crosscheck.csv.

Run: python src/crosscheck_profile.py   (needs CENSUS_API_KEY; the committed CSV is what the Methodology quotes)
"""

import os

import pandas as pd

import acs_config as cfg

COUNTIES = {'12086': 'Miami-Dade', '12087': 'Monroe', '12001': 'Alachua'}
PERIODS = {'2015-2019': 2019, '2020-2024': 2024}
# measure -> (column in data/processed/counties.csv, Data Profile variable)
MEASURES = {
    'home_value': ('home_value_as_published', 'DP04_0089E'),
    'rent': ('rent_as_published', 'DP04_0134E'),
    'income': ('income_as_published', 'DP03_0062E'),
}
PROFILE_URL = 'https://api.census.gov/data/{year}/acs/acs5/profile'


def fetch_profile(year, county_geoid, key, session=None):
    """The three Data Profile medians for one county and release, as {measure: value}"""
    import requests
    import fetch_acs
    session = session or requests
    variables = [v for _, v in MEASURES.values()]
    response = session.get(PROFILE_URL.format(year=year), timeout=60, params={
        'get': 'NAME,' + ','.join(variables), 'for': f'county:{county_geoid[2:]}', 'in': f'state:{cfg.STATE_FIPS}', 'key': key})
    if response.status_code != 200:
        raise RuntimeError(f"Data Profile request failed for {year} {county_geoid}: {fetch_acs.scrub(response.text[:150], key)}")
    header, row = response.json()[0], response.json()[1]
    values = dict(zip(header, row))
    return {measure: int(float(values[var])) for measure, (_, var) in MEASURES.items()}


def compare(counties, profile):
    """
    `counties` is data/processed/counties.csv; `profile` maps (period, county geoid) to {measure: value}.
    Returns one row per county, period and measure with both values and whether they are equal.
    """
    rows = []
    for (period, geoid), values in profile.items():
        row = counties[(counties['period'] == period) & (counties['geoid'] == geoid)].iloc[0]
        for measure, (column, _) in MEASURES.items():
            rows.append({'county': COUNTIES[geoid], 'geoid': geoid, 'period': period, 'measure': measure,
                         'detailed_table_value': int(row[column]), 'data_profile_value': values[measure],
                         'match': int(row[column]) == values[measure]})
    return pd.DataFrame(rows)


def main():
    import fetch_acs
    key = fetch_acs.load_key()
    counties = pd.read_csv(os.path.join(cfg.PROCESSED_DIR, 'counties.csv'), dtype={'geoid': str})
    profile = {(period, geoid): fetch_profile(year, geoid, key) for period, year in PERIODS.items() for geoid in COUNTIES}
    result = compare(counties, profile)
    result.to_csv(cfg.PROFILE_CHECK_PATH, index=False)
    print(result.to_string(index=False))
    print(f"{int(result['match'].sum())} of {len(result)} values match. Wrote {cfg.PROFILE_CHECK_PATH}")


if __name__ == '__main__':
    main()
