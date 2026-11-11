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


def test_a_changed_number_would_be_caught():
    fake = {'home_value_first': 1.0}
    assert findings.money_k(214475.155) == '$214K'
    assert findings.money_k(62808.56, 1) == '$62.8K'
    assert '$1K' in findings.money_k(fake['home_value_first'] * 1000)
