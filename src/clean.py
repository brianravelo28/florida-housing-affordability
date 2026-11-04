"""
Clean the raw ACS responses into the tables the dashboard reads.

Rules (each one is counted; the counts are written to data/processed/cleaning_log.json):
  1. The API's large negative "special values" become missing values, never numbers.
  2. A median whose margin of error is -333333333 is top-coded (the estimate is only the cap), so it is
     flagged and left out of medians and map colors; the cap is kept in its own column.
  3. Reliability: CV = (margin of error / 1.645) / estimate, banded high (<12%), moderate (12-40%),
     low (>40%) using the Census Bureau's ACS handbook convention.
  4. Dollar figures are converted to 2024 dollars. Income and rent use the factors the Census Bureau publishes
     (it adjusts them to each period's final year). Home values from the 2010-2014 and 2015-2019 releases, which
     Census did not adjust, use the average-year CPI-U factor (see acs_config.home_value_factor).
  5. Derived measures: value-to-income ratio (a ratio of two medians, descriptive, no margin of error) and the share
     of renter households paying 30% or more of income on rent, with a margin of error from the Census
     formulas for proportions.
"""

import json
import os

import numpy as np
import pandas as pd

import acs_config as cfg

BANDS = ('high', 'moderate', 'low')


# ---- reading ------------------------------------------------------------------------------------------

def to_frame(rows):
    """API response (header row + data rows) -> DataFrame with numeric variable columns"""
    df = pd.DataFrame(rows[1:], columns=rows[0])
    for variable in cfg.VARIABLES:
        df[variable] = pd.to_numeric(df[variable], errors='coerce')
    return df


def geoid(df, geography):
    if geography == 'state':
        return df['state']
    if geography == 'county':
        return df['state'] + df['county']
    return df['state'] + df['county'] + df['tract']


# ---- rules --------------------------------------------------------------------------------------------

def special(series):
    """True where the API returned a special value (a large negative number) instead of data"""
    return series < cfg.SPECIAL_VALUE_CEILING


def dollars_to_2024(series, api_year, factor=None):
    """Convert dollars as published in the given release to 2024 dollars (Census-published factors by default)"""
    return series * (cfg.DOLLAR_FACTORS_TO_2024[api_year] if factor is None else factor)


def cv_percent(estimate, moe):
    """Coefficient of variation in percent: (MOE / 1.645) / estimate. Missing when it can't be computed."""
    with np.errstate(divide='ignore', invalid='ignore'):
        cv = (moe / cfg.Z_90) / estimate * 100
    return cv.where((estimate > 0) & moe.notna())


def band(cv):
    """Reliability band for each CV; missing CV -> missing"""
    out = pd.Series(np.nan, index=cv.index, dtype='object')
    out[cv < cfg.CV_HIGH_BELOW] = 'high'
    out[(cv >= cfg.CV_HIGH_BELOW) & (cv <= cfg.CV_LOW_ABOVE)] = 'moderate'
    out[cv > cfg.CV_LOW_ABOVE] = 'low'
    return out


def clean_median(df, name, base, api_year, log):
    """One median with its margin of error -> estimate, margin, flag, CV, band, top-code value"""
    est, moe = df[base + 'E'], df[base + 'M']
    no_estimate = est.isna() | (est < 0)
    top_coded = ~no_estimate & (moe == cfg.TOP_CODED_MARGIN)
    ok = ~no_estimate & ~top_coded
    moe_missing = ok & (moe.isna() | (moe < 0))

    out = pd.DataFrame(index=df.index)
    published = est.where(ok)
    margin = moe.where(ok & ~moe_missing)
    factor = cfg.home_value_factor(api_year) if name == 'home_value' else None
    out[name + '_as_published'] = published
    out[name] = dollars_to_2024(published, api_year, factor)
    out[name + '_moe'] = dollars_to_2024(margin, api_year, factor)
    out[name + '_top_code_published'] = est.where(top_coded)
    cv = cv_percent(published, margin)
    out[name + '_cv'] = cv
    reliability = band(cv)
    reliability[no_estimate] = 'no_estimate'
    reliability[top_coded] = 'top_coded'
    reliability[moe_missing] = 'no_margin'
    out[name + '_band'] = reliability

    log[name] = {
        'no_estimate': int(no_estimate.sum()),
        'top_coded': int(top_coded.sum()),
        'estimate_without_margin': int(moe_missing.sum()),
        **{f'band_{b}': int((reliability == b).sum()) for b in BANDS},
    }
    return out


def clean_count(df, name, base, log):
    """A count and its margin of error; special values become missing"""
    est, moe = df[base + 'E'], df[base + 'M']
    bad_est, bad_moe = special(est) | est.isna(), special(moe) | moe.isna()
    log[name] = {'special_estimates': int(bad_est.sum()), 'special_margins': int(bad_moe.sum())}
    return pd.DataFrame({name: est.where(~bad_est), name + '_moe': moe.where(~bad_moe)})


def proportion_moe(numerator, num_moe, denominator, den_moe):
    """
    Margin of error of a proportion p = numerator / denominator where the numerator is a subset of the
    denominator (Census ACS handbook formula). If the term under the root is negative, the ratio formula
    is used instead, as the handbook prescribes.
    """
    p = numerator / denominator
    inside = num_moe ** 2 - p ** 2 * den_moe ** 2
    root = np.sqrt(inside.where(inside >= 0, num_moe ** 2 + p ** 2 * den_moe ** 2))
    return root / denominator


def rent_burden(df, log):
    """Share of renter households (rent computed) paying 30% or more of income on rent, with margin and CV"""
    def col(base, suffix):
        s = df[base + suffix]
        return s.where(~(special(s) | s.isna()))

    parts = cfg.RENT_BURDEN_30PLUS
    num = sum(col(b, 'E') for b in parts)
    num_moe = np.sqrt(sum(col(b, 'M') ** 2 for b in parts))
    total, total_moe = col(cfg.RENT_BURDEN_TOTAL, 'E'), col(cfg.RENT_BURDEN_TOTAL, 'M')
    notcomp, notcomp_moe = col(cfg.RENT_BURDEN_NOT_COMPUTED, 'E'), col(cfg.RENT_BURDEN_NOT_COMPUTED, 'M')
    den = total - notcomp
    den_moe = np.sqrt(total_moe ** 2 + notcomp_moe ** 2)

    valid = den > 0
    share = (num / den).where(valid) * 100
    moe = (proportion_moe(num, num_moe, den, den_moe)).where(valid) * 100
    cv = cv_percent(share, moe)
    reliability = band(cv)
    reliability[~valid] = 'no_estimate'
    reliability[valid & (share == 0)] = 'not_rated'

    log['renters_30plus_share'] = {
        'no_estimate': int((~valid).sum()),
        'share_is_zero': int((valid & (share == 0)).sum()),
        **{f'band_{b}': int((reliability == b).sum()) for b in BANDS},
    }
    return pd.DataFrame({
        'renters_30plus_share': share, 'renters_30plus_share_moe': moe,
        'renters_30plus_share_cv': cv, 'renters_30plus_share_band': reliability,
        'rent_computed_households': den,
    })


def clean_dataset(raw, api_year, geography, period):
    """Raw API frame -> cleaned frame and a log of what each rule did"""
    log = {'rows': int(len(raw))}
    out = pd.DataFrame({
        'geoid': geoid(raw, geography), 'name': raw['NAME'], 'period': period, 'api_year': api_year,
    })
    if geography != 'state':
        out['county_fips'] = raw['county']
    for name, base in cfg.MEDIANS.items():
        out = out.join(clean_median(raw, name, base, api_year, log))
    for name, base in cfg.COUNTS.items():
        out = out.join(clean_count(raw, name, base, log))
    out = out.join(rent_burden(raw, log))

    both = out['home_value'].notna() & out['income'].notna()
    out['value_to_income'] = (out['home_value'] / out['income']).where(both)
    log['value_to_income'] = {'computed': int(both.sum()), 'not_computed': int((~both).sum())}
    return out.reset_index(drop=True), log


# ---- checks -------------------------------------------------------------------------------------------

def assert_no_special_values(df, label):
    """No numeric column may contain an API special value"""
    numeric = df.select_dtypes('number')
    bad = {c: int(special(numeric[c]).sum()) for c in numeric.columns if special(numeric[c]).any()}
    if bad:
        raise AssertionError(f"{label}: special values survived in {bad}")


def sum_mismatches(children, parents, key, columns):
    """
    Count variables must add up from the smaller geography to the larger one. Returns a list of
    (parent id, column, children_sum, parent_value) for every disagreement.
    """
    sums = children.groupby(key)[columns].sum(min_count=1)
    mismatches = []
    for parent_id, row in parents.set_index('geoid').iterrows():
        for column in columns:
            child_sum = sums[column].get(parent_id, np.nan)
            if pd.isna(child_sum) or child_sum != row[column]:
                mismatches.append((parent_id, column, child_sum, row[column]))
    return mismatches


# ---- pipeline -----------------------------------------------------------------------------------------

def period_table():
    """One row per period: the release, the dollar factor, and whether Census adjusted its home values"""
    return pd.DataFrame([{
        'period': period, 'api_year': year, 'dollar_year': cfg.DOLLAR_YEAR,
        'factor_to_2024_dollars': cfg.DOLLAR_FACTORS_TO_2024[year],
        'home_value_adjusted_by_census': year not in cfg.HOME_VALUE_UNADJUSTED_API_YEARS,
        'home_value_factor_to_2024_dollars': cfg.home_value_factor(year),
    } for period, year in cfg.RELEASES.items()])


def read_raw(geography, api_year):
    with open(os.path.join(cfg.RAW_DIR, f'{geography}_{api_year}.json'), encoding='utf-8') as f:
        return to_frame(json.load(f))


def main():
    os.makedirs(cfg.PROCESSED_DIR, exist_ok=True)
    log, states, counties = {}, [], []
    for period, year in cfg.RELEASES.items():
        state, state_log = clean_dataset(read_raw('state', year), year, 'state', period)
        county, county_log = clean_dataset(read_raw('county', year), year, 'county', period)
        log[f'{period} state'], log[f'{period} counties'] = state_log, county_log
        mismatch = sum_mismatches(county.assign(state_id=cfg.STATE_FIPS), state, 'state_id', list(cfg.COUNTS))
        if mismatch:
            raise AssertionError(f"{period}: counties do not add up to the state: {mismatch[:3]}")
        states.append(state)
        counties.append(county)

    latest_year = cfg.RELEASES[cfg.LATEST_PERIOD]
    tracts, tract_log = clean_dataset(read_raw('tract', latest_year), latest_year, 'tract', cfg.LATEST_PERIOD)
    log[f'{cfg.LATEST_PERIOD} tracts'] = tract_log
    latest_counties = counties[-1]
    mismatch = sum_mismatches(tracts.assign(county_geoid=cfg.STATE_FIPS + tracts['county_fips']),
                              latest_counties, 'county_geoid', list(cfg.COUNTS))
    if mismatch:
        raise AssertionError(f"tracts do not add up to counties: {mismatch[:3]}")

    outputs = {
        'state.csv': pd.concat(states, ignore_index=True),
        'counties.csv': pd.concat(counties, ignore_index=True),
        f'tracts_{cfg.LATEST_PERIOD}.csv': tracts,
        'periods.csv': period_table(),
    }
    for filename, frame in outputs.items():
        assert_no_special_values(frame, filename)
        frame.to_csv(os.path.join(cfg.PROCESSED_DIR, filename), index=False, float_format='%.10g')
        print(f"{filename}: {len(frame):,} rows")
    with open(os.path.join(cfg.PROCESSED_DIR, 'cleaning_log.json'), 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)
    print("Wrote cleaning_log.json")


if __name__ == '__main__':
    main()
