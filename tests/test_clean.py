"""
Cleaning rules, with small hand-built fixtures. No network, no API key.
"""

import numpy as np
import pandas as pd
import pytest

import acs_config as cfg
import clean

SENT_NA, SENT_NO_MOE, SENT_TOP = -666666666, -222222222, -333333333


# ---- special values ------------------------------------------------------------------------------------

def test_not_available_estimate_becomes_missing_and_is_flagged(make_raw, cleaned):
    raw = make_raw({'B25077_001E': SENT_NA, 'B25077_001M': SENT_NO_MOE})
    out = cleaned(raw)
    assert out['home_value'].isna().all() and out['home_value_moe'].isna().all()
    assert out['home_value_band'].iloc[0] == 'no_estimate'
    assert out.select_dtypes('number').min().min() > cfg.SPECIAL_VALUE_CEILING  # no special value left in any column


def test_top_coded_median_is_flagged_and_kept_out_of_values(make_raw, cleaned):
    raw = make_raw({'B25077_001E': 2000001, 'B25077_001M': SENT_TOP, 'B19013_001E': 80000})
    out = cleaned(raw)
    assert out['home_value'].isna().all()
    assert out['home_value_band'].iloc[0] == 'top_coded'
    assert out['home_value_top_code_published'].iloc[0] == 2000001
    assert out['value_to_owner_income'].isna().all()  # a top-coded value must not feed the ratio


def test_estimate_with_unavailable_margin_is_kept_but_not_rated(make_raw, cleaned):
    out = cleaned(make_raw({'B25064_001E': 1500, 'B25064_001M': SENT_NO_MOE}))
    assert out['rent_as_published'].iloc[0] == 1500
    assert out['rent_band'].iloc[0] == 'no_margin'
    assert pd.isna(out['rent_cv'].iloc[0])


def test_special_values_in_counts_become_missing_and_are_logged(make_raw):
    raw = make_raw({'B25001_001E': SENT_NA, 'B25001_001M': SENT_NO_MOE})
    out, log = clean.clean_dataset(raw, 2024, 'tract', '2020-2024')
    assert out['housing_units'].isna().all()
    assert log['housing_units'] == {'special_estimates': 1, 'special_margins': 1}


def test_a_surviving_special_value_is_caught():
    df = pd.DataFrame({'a': [1.0, -666666666.0]})
    with pytest.raises(AssertionError, match='special values'):
        clean.assert_no_special_values(df, 'test')
    clean.assert_no_special_values(pd.DataFrame({'a': [1.0, -5.0]}), 'test')  # ordinary negatives are not special


# ---- reliability ---------------------------------------------------------------------------------------

def test_cv_formula():
    cv = clean.cv_percent(pd.Series([100000.0]), pd.Series([16450.0]))  # SE = 16450/1.645 = 10000
    assert cv.iloc[0] == pytest.approx(10.0)


def test_cv_is_missing_without_a_positive_estimate_or_margin():
    cv = clean.cv_percent(pd.Series([0.0, 100.0, np.nan]), pd.Series([5.0, np.nan, 5.0]))
    assert cv.isna().all()


@pytest.mark.parametrize('cv,expected', [(0.0, 'high'), (11.99, 'high'), (12.0, 'moderate'),
                                         (40.0, 'moderate'), (40.01, 'low'), (150.0, 'low')])
def test_band_edges_follow_the_documented_cutoffs(cv, expected):
    assert clean.band(pd.Series([cv])).iloc[0] == expected


def test_band_counts_are_logged(make_raw):
    # CVs of 10%, 20% and 50% (SE = MOE / 1.645)
    raw = make_raw({'B19013_001E': 100000, 'B19013_001M': 16450},
                   {'B19013_001E': 100000, 'B19013_001M': 32900},
                   {'B19013_001E': 100000, 'B19013_001M': 82250})
    _, log = clean.clean_dataset(raw, 2024, 'tract', '2020-2024')
    assert (log['income']['band_high'], log['income']['band_moderate'], log['income']['band_low']) == (1, 1, 1)


# ---- dollars -------------------------------------------------------------------------------------------

def test_factors_chain_the_two_published_census_factors():
    assert cfg.DOLLAR_FACTORS_TO_2024[2024] == 1.0
    assert cfg.DOLLAR_FACTORS_TO_2024[2019] == pytest.approx(1.23070782)
    assert cfg.DOLLAR_FACTORS_TO_2024[2014] == pytest.approx(1.08096469 * 1.23070782)
    assert cfg.DOLLAR_FACTORS_TO_2024[2014] == pytest.approx(1.330352, abs=1e-6)


def test_dollars_convert_estimate_and_margin_and_leave_cv_alone(make_raw, cleaned):
    raw = make_raw({'B19013_001E': 50000, 'B19013_001M': 5000})
    out = cleaned(raw, api_year=2019)
    assert out['income_as_published'].iloc[0] == 50000
    assert out['income'].iloc[0] == pytest.approx(50000 * 1.23070782)
    assert out['income_moe'].iloc[0] == pytest.approx(5000 * 1.23070782)
    assert out['income_cv'].iloc[0] == pytest.approx(5000 / 1.645 / 50000 * 100)


def test_cpi_u_averages_reproduce_the_factors_census_publishes():
    cpi = cfg.CPI_U_ANNUAL_AVERAGE
    assert cpi[2024] / cpi[2019] == pytest.approx(1.23070782, rel=0.005)
    assert cpi[2019] / cpi[2014] == pytest.approx(1.08096469, rel=0.005)


def test_unadjusted_home_values_use_the_average_year_factor():
    cpi = cfg.CPI_U_ANNUAL_AVERAGE
    expected_2014 = cpi[2024] / ((cpi[2010] + cpi[2011] + cpi[2012] + cpi[2013] + cpi[2014]) / 5)
    expected_2019 = cpi[2024] / ((cpi[2015] + cpi[2016] + cpi[2017] + cpi[2018] + cpi[2019]) / 5)
    assert cfg.home_value_factor(2014) == pytest.approx(expected_2014)
    assert cfg.home_value_factor(2019) == pytest.approx(expected_2019)
    assert cfg.home_value_factor(2014) == pytest.approx(1.3731, abs=1e-4)
    # larger than the final-year factor: the values were reported earlier in the window
    assert cfg.home_value_factor(2014) > cfg.DOLLAR_FACTORS_TO_2024[2014]
    assert cfg.home_value_factor(2019) > cfg.DOLLAR_FACTORS_TO_2024[2019]


def test_census_adjusted_home_values_keep_the_published_factor():
    assert cfg.home_value_factor(2024) == 1.0


def test_home_value_and_income_use_different_factors_in_an_unadjusted_release(make_raw, cleaned):
    out = cleaned(make_raw({'B25077_001E': 156200, 'B25077_001M': 1000, 'B19013_001E': 47212, 'B19013_001M': 500}),
                  api_year=2014)
    assert out['home_value'].iloc[0] == pytest.approx(156200 * cfg.home_value_factor(2014))
    assert out['home_value_moe'].iloc[0] == pytest.approx(1000 * cfg.home_value_factor(2014))
    assert out['income'].iloc[0] == pytest.approx(47212 * cfg.DOLLAR_FACTORS_TO_2024[2014])  # Census adjusted income
    assert out['home_value_as_published'].iloc[0] == 156200


def test_rent_keeps_the_published_factor_in_an_unadjusted_release(make_raw, cleaned):
    out = cleaned(make_raw({'B25064_001E': 1000}), api_year=2019)
    assert out['rent'].iloc[0] == pytest.approx(1000 * 1.23070782)


def test_unadjusted_home_value_matches_the_measured_florida_figure():
    # Florida 2010-2014 published median $156,200 -> about $214,500 in 2024 dollars (measured two independent ways)
    assert 156200 * cfg.home_value_factor(2014) == pytest.approx(214_450, abs=100)


def test_latest_release_dollars_are_unchanged(make_raw, cleaned):
    out = cleaned(make_raw({'B25064_001E': 1700}), api_year=2024)
    assert out['rent'].iloc[0] == 1700


def test_period_table_states_which_home_values_census_adjusted():
    table = clean.period_table().set_index('period')
    assert table['home_value_adjusted_by_census'].to_dict() == {'2010-2014': False, '2015-2019': False, '2020-2024': True}
    assert table.loc['2015-2019', 'factor_to_2024_dollars'] == pytest.approx(1.23070782)
    assert table.loc['2015-2019', 'home_value_factor_to_2024_dollars'] == pytest.approx(cfg.home_value_factor(2019))
    assert table.loc['2020-2024', 'home_value_factor_to_2024_dollars'] == 1.0


# ---- derived measures ----------------------------------------------------------------------------------

def test_value_to_owner_income_ratio(make_raw, cleaned):
    out = cleaned(make_raw({'B25077_001E': 400000, 'B25119_002E': 80000},
                           {'B25077_001E': 400000, 'B25119_002E': SENT_NA, 'B25119_002M': SENT_NO_MOE}))
    assert out['value_to_owner_income'].iloc[0] == pytest.approx(5.0)
    assert pd.isna(out['value_to_owner_income'].iloc[1])


def test_the_ratio_divides_by_owner_income_not_all_household_income(make_raw, cleaned):
    """Home value covers owner-occupied homes only, so the denominator is the income of owner households"""
    out = cleaned(make_raw({'B25077_001E': 300000, 'B19013_001E': 60000, 'B25119_002E': 75000}))
    assert out['value_to_owner_income'].iloc[0] == pytest.approx(4.0)   # 300000 / 75000, not 300000 / 60000
    assert out['income'].iloc[0] == 60000                              # the all-household median is still reported


def test_value_to_owner_income_compares_values_in_the_same_2024_dollars(make_raw, cleaned):
    raw = make_raw({'B25077_001E': 300000, 'B25119_002E': 60000})
    ratio = cleaned(raw, api_year=2014)['value_to_owner_income'].iloc[0]
    expected = (300000 * cfg.home_value_factor(2014)) / (60000 * cfg.DOLLAR_FACTORS_TO_2024[2014])
    assert ratio == pytest.approx(expected)
    assert ratio > 5.0  # the early home value is converted with a larger factor than income, so the ratio is above the raw 5.0


def test_the_lowest_and_highest_open_ended_intervals_are_told_apart(make_raw, cleaned):
    out = cleaned(make_raw({'B25119_002E': 2499, 'B25119_002M': SENT_TOP},
                           {'B25119_002E': 250001, 'B25119_002M': SENT_TOP},
                           {'B25119_002E': 90000, 'B25119_002M': 900}))
    assert out['owner_income_open_end'].iloc[0] == 'below'
    assert out['owner_income_open_end'].iloc[1] == 'above'
    assert pd.isna(out['owner_income_open_end'].iloc[2])
    assert (out['owner_income_band'].iloc[:2] == 'top_coded').all()


def test_bottom_coded_counts_are_logged(make_raw):
    raw = make_raw({'B25119_002E': 2499, 'B25119_002M': SENT_TOP}, {'B25119_002E': 250001, 'B25119_002M': SENT_TOP})
    _, log = clean.clean_dataset(raw, 2024, 'tract', '2020-2024')
    assert log['owner_income']['top_coded'] == 2 and log['owner_income']['of_which_bottom_coded'] == 1


def test_proportion_moe_matches_a_hand_calculation():
    # p = 30/100; sqrt(6^2 - 0.3^2 * 10^2) / 100 = sqrt(27) / 100
    moe = clean.proportion_moe(pd.Series([30.0]), pd.Series([6.0]), pd.Series([100.0]), pd.Series([10.0]))
    assert moe.iloc[0] == pytest.approx(np.sqrt(27) / 100)


def test_proportion_moe_falls_back_to_the_ratio_formula_when_the_root_would_be_negative():
    # 1^2 - 0.05^2 * 40^2 < 0, so use sqrt(1^2 + 0.05^2 * 40^2) / 100 = sqrt(5) / 100
    moe = clean.proportion_moe(pd.Series([5.0]), pd.Series([1.0]), pd.Series([100.0]), pd.Series([40.0]))
    assert moe.iloc[0] == pytest.approx(np.sqrt(5) / 100)


def test_rent_burden_share_and_margin(make_raw, cleaned):
    overrides = {'B25070_001E': 200, 'B25070_011E': 20,                      # 180 renters with rent computed
                 'B25070_007E': 20, 'B25070_008E': 20, 'B25070_009E': 10, 'B25070_010E': 10,  # 60 paying 30%+
                 'B25070_007M': 4, 'B25070_008M': 4, 'B25070_009M': 4, 'B25070_010M': 4,
                 'B25070_001M': 6, 'B25070_011M': 8}
    out = cleaned(make_raw(overrides))
    assert out['renters_30plus_share'].iloc[0] == pytest.approx(60 / 180 * 100)
    num_moe, den_moe, p = 8.0, 10.0, 60 / 180   # sqrt(4 * 4^2) = 8; sqrt(6^2 + 8^2) = 10
    expected = np.sqrt(num_moe ** 2 - p ** 2 * den_moe ** 2) / 180 * 100
    assert out['renters_30plus_share_moe'].iloc[0] == pytest.approx(expected)
    assert out['rent_computed_households'].iloc[0] == 180


def test_rent_burden_with_no_renters_is_not_an_estimate(make_raw, cleaned):
    out = cleaned(make_raw({'B25070_001E': 0, 'B25070_011E': 0, 'B25070_007E': 0, 'B25070_008E': 0,
                            'B25070_009E': 0, 'B25070_010E': 0}))
    assert pd.isna(out['renters_30plus_share'].iloc[0])
    assert out['renters_30plus_share_band'].iloc[0] == 'no_estimate'


def test_geoids_are_built_from_the_codes(make_raw, cleaned):
    out = cleaned(make_raw({}))
    assert out['geoid'].iloc[0] == '12086000000'
    county = cleaned(make_raw({}), geography='county')
    assert county['geoid'].iloc[0] == '12086'


# ---- reading -------------------------------------------------------------------------------------------

def test_to_frame_turns_json_nulls_and_strings_into_numbers():
    header = ['NAME'] + cfg.VARIABLES + ['state', 'county']
    row = ['X'] + [None] * len(cfg.VARIABLES) + ['12', '001']
    row[1 + cfg.VARIABLES.index('B25077_001E')] = '250000'
    df = clean.to_frame([header, row])
    assert df['B25077_001E'].iloc[0] == 250000
    assert df['B25077_001M'].isna().iloc[0]
    assert df['county'].iloc[0] == '001'


# ---- add-up checks -------------------------------------------------------------------------------------

def test_counts_that_add_up_pass():
    children = pd.DataFrame({'parent': ['a', 'a', 'b'], 'n': [3, 4, 5]})
    parents = pd.DataFrame({'geoid': ['a', 'b'], 'n': [7, 5]})
    assert clean.sum_mismatches(children, parents, 'parent', ['n']) == []


def test_counts_off_by_one_are_reported():
    children = pd.DataFrame({'parent': ['a', 'a'], 'n': [3, 4]})
    parents = pd.DataFrame({'geoid': ['a'], 'n': [8]})
    assert clean.sum_mismatches(children, parents, 'parent', ['n']) == [('a', 'n', 7, 8)]


def test_a_parent_with_no_children_is_reported():
    children = pd.DataFrame({'parent': ['a'], 'n': [1]})
    parents = pd.DataFrame({'geoid': ['a', 'b'], 'n': [1, 2]})
    assert [m[0] for m in clean.sum_mismatches(children, parents, 'parent', ['n'])] == ['b']
