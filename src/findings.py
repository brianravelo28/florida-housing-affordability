"""
The headline numbers quoted in the README, computed from the processed tables.

Run: python src/findings.py   (after python run_pipeline.py). It writes data/processed/findings.csv, and
tests/test_findings.py checks that the README contains every number listed in readme_facts().
"""

import os

import numpy as np
import pandas as pd

import acs_config as cfg
import view

PERIOD_FIRST, PERIOD_MID, PERIOD_LAST = '2010-2014', '2015-2019', '2020-2024'
RANK_COUNT = 5


def read_tables(directory=None):
    directory = directory or cfg.PROCESSED_DIR
    read = lambda name: pd.read_csv(os.path.join(directory, name), dtype={'geoid': str, 'county_fips': str})
    return read('state.csv'), read('counties.csv'), read(f'tracts_{PERIOD_LAST}.csv')


def usable_ratio(df):
    """Rows where both medians behind the home value to owner income ratio are reliable enough to map"""
    return ~df['home_value_band'].isin(view.GRAY_BANDS) & ~df['owner_income_band'].isin(view.GRAY_BANDS)


def ratio_margin(value, value_moe, income, income_moe):
    """
    Approximate 90% margin of error of the ratio value / income, from the Census Bureau's formula for a ratio:
    sqrt(moe_value^2 + ratio^2 * moe_income^2) / income. The formula assumes the two medians are independent; they
    come from the same survey, so this is an approximation used only to judge differences, not shown on the map.
    """
    ratio = value / income
    return np.sqrt(value_moe ** 2 + ratio ** 2 * income_moe ** 2) / income


def county_ratios(counties, period):
    """One row per county: name, ratio and its approximate margin, for one period"""
    d = counties[counties['period'] == period]
    out = pd.DataFrame({'geoid': d['geoid'].values, 'name': d['name'].map(view.short_name).str.replace(' County', '').values,
                        'ratio': d['value_to_owner_income'].values}, index=d.index)
    out['margin'] = ratio_margin(d['home_value'], d['home_value_moe'], d['owner_income'], d['owner_income_moe'])
    return out.reset_index(drop=True)


def separated(ratio_a, margin_a, ratio_b, margin_b):
    """True when two ratios differ by more than their combined margin of error"""
    return abs(ratio_a - ratio_b) > np.sqrt(margin_a ** 2 + margin_b ** 2)


def compute(state, counties, tracts):
    """Flat dict of named numbers (and county names) behind the README findings"""
    s = state.set_index('period')
    out = {}
    for period, tag in ((PERIOD_FIRST, 'first'), (PERIOD_MID, 'mid'), (PERIOD_LAST, 'last')):
        out[f'home_value_{tag}'] = s.loc[period, 'home_value']
        out[f'owner_income_{tag}'] = s.loc[period, 'owner_income']
        # sensitivity: the same ratio with the income of all households (owners and renters) as the denominator
        out[f'ratio_all_households_{tag}'] = s.loc[period, 'home_value'] / s.loc[period, 'income']
        out[f'rent_{tag}'] = s.loc[period, 'rent']
        out[f'ratio_{tag}'] = s.loc[period, 'value_to_owner_income']
        out[f'renter_share_{tag}'] = s.loc[period, 'renters_30plus_share']
    out['renter_share_moe_last'] = s.loc[PERIOD_LAST, 'renters_30plus_share_moe']
    for measure in ('home_value', 'owner_income', 'rent'):
        out[f'{measure}_growth_pct'] = (out[f'{measure}_last'] / out[f'{measure}_first'] - 1) * 100

    latest = counties[counties['period'] == PERIOD_LAST]
    usable = latest[usable_ratio(latest)].sort_values('value_to_owner_income', ascending=False)
    out['counties_with_ratio'] = len(usable)
    for rank, (_, row) in enumerate(usable.head(RANK_COUNT).iterrows(), 1):
        out[f'top_ratio_{rank}_county'] = view.short_name(row['name']).replace(' County', '')
        out[f'top_ratio_{rank}'] = row['value_to_owner_income']
    for rank, (_, row) in enumerate(usable.tail(3).sort_values('value_to_owner_income').iterrows(), 1):
        out[f'low_ratio_{rank}_county'] = view.short_name(row['name']).replace(' County', '')
        out[f'low_ratio_{rank}'] = row['value_to_owner_income']

    pivot = counties.pivot(index='geoid', columns='period', values='value_to_owner_income')
    change = (pivot[PERIOD_LAST] - pivot[PERIOD_FIRST]).dropna()
    out['counties_ratio_rose'] = int((change > 0).sum())
    out['counties_ratio_compared'] = len(change)
    first, last = county_ratios(counties, PERIOD_FIRST).set_index('geoid'), county_ratios(counties, PERIOD_LAST).set_index('geoid')
    shift = (last['ratio'] - first['ratio']).dropna()
    combined = np.sqrt(last['margin'] ** 2 + first['margin'] ** 2).reindex(shift.index)
    out['counties_ratio_rose_beyond_margin'] = int((shift > combined).sum())
    out['counties_ratio_fell'] = int((shift < 0).sum())
    out['counties_ratio_fell_beyond_margin'] = int((-shift > combined).sum())

    ok = tracts[usable_ratio(tracts)]
    ratio = ok['value_to_owner_income']
    out['tracts_total'] = len(tracts)
    out['tracts_with_ratio'] = len(ok)
    out['tracts_ratio_5x_pct'] = (ratio >= 5).mean() * 100
    out['tracts_ratio_6x_pct'] = (ratio >= 6).mean() * 100
    return out


def money_k(value, decimals=0):
    return f"${value / 1000:,.{decimals}f}K"


def readme_facts(f):
    """The strings the README findings must contain, built from the computed numbers"""
    facts = [
        money_k(f['home_value_first']), money_k(f['home_value_last']), f"{f['home_value_growth_pct']:.0f}%",
        money_k(f['owner_income_first'], 1), money_k(f['owner_income_last'], 1), f"{f['owner_income_growth_pct']:.0f}%",
        f"{f['ratio_first']:.1f}", f"{f['ratio_mid']:.1f}", f"{f['ratio_last']:.1f}",
        f"${f['rent_first']:,.0f}", f"${f['rent_last']:,.0f}", f"{f['rent_growth_pct']:.0f}%",
        f"{f['renter_share_first']:.1f}%", f"{f['renter_share_mid']:.1f}%", f"{f['renter_share_last']:.1f}%",
        f"{f['counties_ratio_rose']} of {f['counties_ratio_compared']}", f"in {f['counties_ratio_rose_beyond_margin']} of them",
        f"{f['tracts_with_ratio']:,}", f"{f['tracts_ratio_5x_pct']:.0f}%", f"{f['tracts_ratio_6x_pct']:.1f}%",
    ]
    for rank in range(1, RANK_COUNT + 1):
        facts += [f[f'top_ratio_{rank}_county'], f"{f[f'top_ratio_{rank}']:.1f}"]
    for rank in range(1, 4):
        facts.append(f[f'low_ratio_{rank}_county'])
    facts.append(f"{f['low_ratio_1']:.1f}")
    return facts


def main():
    findings = compute(*read_tables())
    path = os.path.join(cfg.PROCESSED_DIR, 'findings.csv')
    pd.DataFrame({'name': list(findings), 'value': [findings[k] for k in findings]}).to_csv(
        path, index=False, float_format='%.10g')
    for name, value in findings.items():
        print(f"{name}: {value}")
    print(f"Wrote {path}")


if __name__ == '__main__':
    main()
