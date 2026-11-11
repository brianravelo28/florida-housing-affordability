"""
The numbers quoted in the README must match the data: findings.csv is what findings.py computes from the processed
tables, and the README contains every number findings.py says it should.
"""

import os

import pandas as pd
import pytest

import acs_config as cfg
import findings

ROOT = cfg.ROOT
FINDINGS_CSV = os.path.join(cfg.PROCESSED_DIR, 'findings.csv')


@pytest.fixture(scope='module')
def computed():
    return findings.compute(*findings.read_tables())


def test_committed_findings_match_what_the_code_computes(computed):
    committed = pd.read_csv(FINDINGS_CSV).set_index('name')['value']
    assert list(committed.index) == list(computed)
    for name, value in computed.items():
        if isinstance(value, str):
            assert committed[name] == value
        else:
            assert float(committed[name]) == pytest.approx(value, rel=1e-6)


def test_readme_contains_every_number_the_findings_produce(computed):
    readme = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
    missing = [fact for fact in findings.readme_facts(computed) if fact not in readme]
    assert not missing, f"README is missing or has changed: {missing}"


def test_findings_are_internally_consistent(computed):
    assert computed['home_value_growth_pct'] > computed['owner_income_growth_pct']
    assert computed['counties_with_ratio'] == 67
    assert computed['tracts_with_ratio'] <= computed['tracts_total'] == 5160
    assert computed['tracts_ratio_5x_pct'] >= computed['tracts_ratio_6x_pct']
    ratios = [computed[f'top_ratio_{i}'] for i in range(1, findings.RANK_COUNT + 1)]
    assert ratios == sorted(ratios, reverse=True)


def test_ratio_margin_matches_a_hand_calculation():
    # ratio 4; sqrt(30000^2 + 4^2 * 4000^2) / 100000 = sqrt(9e8 + 2.56e8) / 1e5 = 34000 / 1e5
    assert findings.ratio_margin(400000, 30000, 100000, 4000) == pytest.approx(0.34)


def test_two_ratios_are_separated_only_when_they_differ_by_more_than_the_combined_margin():
    assert findings.separated(5.0, 0.3, 4.0, 0.4)        # gap 1.0 > sqrt(0.09 + 0.16) = 0.5
    assert not findings.separated(5.0, 0.3, 4.8, 0.4)    # gap 0.2 < 0.5


def test_counts_of_changes_are_consistent(computed):
    assert computed['counties_ratio_rose_beyond_margin'] <= computed['counties_ratio_rose']
    assert computed['counties_ratio_fell'] + computed['counties_ratio_rose'] <= computed['counties_ratio_compared']
    assert computed['counties_ratio_fell_beyond_margin'] <= computed['counties_ratio_fell']


@pytest.fixture(scope='module')
def latest_ratios():
    _, counties, _ = findings.read_tables()
    table = findings.county_ratios(counties, findings.PERIOD_LAST)
    usable = table[findings.usable_ratio(counties[counties['period'] == findings.PERIOD_LAST]).values]
    return usable.sort_values('ratio', ascending=False).reset_index(drop=True)


def test_claim_monroe_and_collier_are_clearly_above_every_other_county(latest_ratios):
    t = latest_ratios
    assert list(t['name'][:2]) == ['Monroe', 'Collier']
    assert findings.separated(t.ratio[0], t.margin[0], t.ratio[1], t.margin[1])
    for i in range(2, len(t)):
        assert findings.separated(t.ratio[1], t.margin[1], t.ratio[i], t.margin[i]), t['name'][i]


def test_claim_the_next_three_counties_cannot_be_told_apart(latest_ratios):
    t = latest_ratios
    assert list(t['name'][2:5]) == ['Miami-Dade', 'Walton', 'Sumter']
    for i, j in ((2, 3), (3, 4), (2, 4)):
        assert not findings.separated(t.ratio[i], t.margin[i], t.ratio[j], t.margin[j])


def test_claim_the_lowest_three_counties_cannot_be_told_apart(latest_ratios):
    t = latest_ratios.iloc[::-1].reset_index(drop=True)
    assert list(t['name'][:3]) == ['Liberty', 'Madison', 'Taylor']
    for i, j in ((0, 1), (1, 2), (0, 2)):
        assert not findings.separated(t.ratio[i], t.margin[i], t.ratio[j], t.margin[j])


def test_a_changed_number_would_be_caught():
    fake = {'home_value_first': 1.0}
    assert findings.money_k(214475.155) == '$214K'
    assert findings.money_k(62808.56, 1) == '$62.8K'
    assert '$1K' in findings.money_k(fake['home_value_first'] * 1000)
