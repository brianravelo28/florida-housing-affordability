"""
The check of the early home-value conversion and the Data Profile cross-check: the logic with small hand-built numbers, the
committed results against what the code recomputes, and the claims the documentation makes about them.
"""

import numpy as np
import pandas as pd
import pytest

import acs_config as cfg
import crosscheck_profile as cc
import home_value_conversion_check as check

CPI = {**{y: 100.0 + (y - 2010) for y in range(2010, 2020)}, 2024: 150.0}   # 2010..2019 = 100..109, 2024 = 150
STATE = pd.DataFrame({'period': ['2010-2014', '2015-2019', '2020-2024'],
                      'home_value_as_published': [100000, 150000, 300000], 'home_value': [0, 0, 300000]})
ONE_YEAR = pd.DataFrame({'year': range(2010, 2020), 'median_home_value': [100000] * 10})


# ---- the conversion check ------------------------------------------------------------------------------

def test_factors_and_converted_values_match_a_hand_calculation():
    row = check.conversion_check(STATE, ONE_YEAR, cpi=CPI).set_index('period').loc['2010-2014']
    average_cpi = (100 + 101 + 102 + 103 + 104) / 5                      # 102
    assert row['factor_average_year'] == pytest.approx(150 / average_cpi)
    assert row['factor_final_year_cpi'] == pytest.approx(150 / 104)
    assert row['converted_average_year'] == pytest.approx(100000 * 150 / 102)
    assert row['converted_final_year_cpi'] == pytest.approx(100000 * 150 / 104)
    # the average-year conversion is larger than the final-year one by the ratio of the two CPI levels
    assert row['understatement_pct_cpi'] == pytest.approx((104 / 102 - 1) * 100)


def test_growth_overstatement_is_the_difference_between_the_two_growth_figures():
    row = check.conversion_check(STATE, ONE_YEAR, cpi=CPI).set_index('period').loc['2010-2014']
    used, final = 100000 * 150 / 102, 100000 * 150 / 104
    assert row['growth_pct_average_year'] == pytest.approx((300000 / used - 1) * 100)
    assert row['growth_overstatement_points_cpi'] == pytest.approx((300000 / final - 1) * 100 - (300000 / used - 1) * 100)


def test_the_second_method_converts_each_year_with_its_own_cpi_and_averages():
    row = check.conversion_check(STATE, ONE_YEAR, cpi=CPI).set_index('period').loc['2010-2014']
    expected = np.mean([100000 * 150 / (100 + i) for i in range(5)])
    assert row['converted_yearly_medians'] == pytest.approx(expected)
    assert row['method_gap_pct'] == pytest.approx((expected / (100000 * 150 / 102) - 1) * 100)


def test_flat_prices_and_flat_cpi_give_no_difference_between_methods():
    flat = {**{y: 100.0 for y in range(2010, 2020)}, 2024: 150.0}
    row = check.conversion_check(STATE, ONE_YEAR, cpi=flat).iloc[0]
    assert row['understatement_pct_cpi'] == pytest.approx(0.0) and row['method_gap_pct'] == pytest.approx(0.0)


def test_fetching_the_single_year_medians_parses_and_does_not_leak_the_key():
    class Session:
        def __init__(self, status): self.status = status
        def get(self, url, params=None, timeout=None):
            class R:
                status_code = self.status
                text = 'bad key SECRET'
                def json(inner): return [['B25077_001E', 'state'], ['164200', '12']]
            return R()
    medians = check.fetch_one_year_medians('SECRET', years=[2010, 2011], session=Session(200))
    assert medians['median_home_value'].tolist() == [164200, 164200] and medians['year'].tolist() == [2010, 2011]
    with pytest.raises(RuntimeError) as failed:
        check.fetch_one_year_medians('SECRET', years=[2010], session=Session(401))
    assert 'SECRET' not in str(failed.value)


# ---- committed results ---------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def committed():
    return pd.read_csv(cfg.CONVERSION_CHECK_PATH)


def test_the_stored_single_year_medians_cover_2010_to_2019_once_each():
    stored = pd.read_csv(cfg.ONE_YEAR_MEDIANS_PATH)
    assert sorted(stored['year']) == list(range(2010, 2020)) and (stored['median_home_value'] > 0).all()


def test_the_committed_conversion_check_is_what_the_code_computes(committed):
    state = pd.read_csv(f'{cfg.PROCESSED_DIR}/state.csv')
    recomputed = check.conversion_check(state, pd.read_csv(cfg.ONE_YEAR_MEDIANS_PATH))
    pd.testing.assert_frame_equal(committed, recomputed, rtol=1e-6, check_dtype=False)


def test_the_average_year_factor_used_by_the_pipeline_is_the_one_checked(committed):
    for _, row in committed.iterrows():
        year = cfg.RELEASES[row['period']]
        assert row['factor_average_year'] == pytest.approx(cfg.home_value_factor(year))


def test_claim_final_year_conversion_understates_by_three_to_four_percent(committed):
    values = committed[['understatement_pct_census', 'understatement_pct_cpi']].to_numpy().ravel()
    assert 3.0 <= values.min() and values.max() <= 4.1


def test_claim_growth_is_overstated_by_about_five_to_six_points(committed):
    values = committed[['growth_overstatement_points_census', 'growth_overstatement_points_cpi']].to_numpy().ravel()
    assert 4.5 <= values.min() and values.max() <= 6.5


def test_claim_the_second_method_is_within_about_one_percent(committed):
    assert committed['method_gap_pct'].abs().max() <= 1.2


def test_claim_cpi_factors_are_within_half_a_percent_of_the_census_factors(committed):
    assert committed['cpi_vs_census_factor_pct'].abs().max() <= 0.5


# ---- the Data Profile cross-check ----------------------------------------------------------------------

COUNTIES = pd.DataFrame({'period': ['2020-2024'], 'geoid': ['12086'], 'home_value_as_published': [463000],
                         'rent_as_published': [1829], 'income_as_published': [71753]})


def test_compare_marks_agreement_and_disagreement():
    result = cc.compare(COUNTIES, {('2020-2024', '12086'): {'home_value': 463000, 'rent': 1830, 'income': 71753}})
    assert result.set_index('measure')['match'].to_dict() == {'home_value': True, 'rent': False, 'income': True}
    assert (result['county'] == 'Miami-Dade').all()


def test_the_profile_request_uses_the_right_geography_and_variables():
    seen = {}

    class Session:
        def get(self, url, params=None, timeout=None):
            seen.update(url=url, params=params)
            class R:
                status_code = 200
                def json(inner): return [['NAME', 'DP04_0089E', 'DP04_0134E', 'DP03_0062E', 'state', 'county'],
                                         ['x', '463000', '1829', '71753', '12', '086']]
            return R()
    values = cc.fetch_profile(2024, '12086', 'KEY', session=Session())
    assert values == {'home_value': 463000, 'rent': 1829, 'income': 71753}
    assert seen['url'].endswith('/2024/acs/acs5/profile') and seen['params']['for'] == 'county:086'


def test_the_committed_cross_check_has_all_eighteen_values_and_they_match_the_data():
    result = pd.read_csv(cfg.PROFILE_CHECK_PATH, dtype={'geoid': str})
    assert len(result) == 18 and result['match'].all()
    assert set(result['county']) == {'Miami-Dade', 'Monroe', 'Alachua'} and set(result['period']) == {'2015-2019', '2020-2024'}
    counties = pd.read_csv(f'{cfg.PROCESSED_DIR}/counties.csv', dtype={'geoid': str})
    for _, row in result.iterrows():
        column = cc.MEASURES[row['measure']][0]
        published = counties[(counties['period'] == row['period']) & (counties['geoid'] == row['geoid'])][column].iloc[0]
        assert published == row['detailed_table_value'] == row['data_profile_value']
