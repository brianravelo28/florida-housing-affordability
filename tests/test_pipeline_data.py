"""
The committed data against the pipeline: raw snapshots match their checksums, the processed tables are exactly what the cleaning
code writes from them, the cleaning is deterministic, and the keys and geographies are the expected ones.
"""

import hashlib
import json
import os

import pandas as pd
import pytest

import acs_config as cfg
import clean

RAW = cfg.RAW_DIR


def read_processed(name):
    return pd.read_csv(os.path.join(cfg.PROCESSED_DIR, name), dtype={'geoid': str, 'county_fips': str})


# ---- raw snapshots and the manifest -----------------------------------------------------------------

def test_every_manifest_entry_matches_its_raw_snapshot():
    manifest = json.load(open(cfg.MANIFEST_PATH, encoding='utf-8'))
    assert len(manifest) == 7
    for entry in manifest:
        path = os.path.join(cfg.ROOT, entry['raw_file'])
        assert hashlib.sha256(open(path, 'rb').read()).hexdigest() == entry['sha256'], entry['raw_file']
        rows = json.load(open(path, encoding='utf-8'))
        assert len(rows) - 1 == entry['rows'] and rows[0][0] == 'NAME'


def test_raw_snapshots_contain_every_variable_the_pipeline_requests():
    header = json.load(open(os.path.join(RAW, 'tract_2024.json'), encoding='utf-8'))[0]
    assert set(cfg.VARIABLES) <= set(header)


# ---- the committed tables are what the code writes from the snapshots --------------------------------

def rebuilt():
    states, counties = [], []
    for period, year in cfg.RELEASES.items():
        states.append(clean.clean_dataset(clean.read_raw('state', year), year, 'state', period)[0])
        counties.append(clean.clean_dataset(clean.read_raw('county', year), year, 'county', period)[0])
    latest = cfg.RELEASES[cfg.LATEST_PERIOD]
    tracts = clean.clean_dataset(clean.read_raw('tract', latest), latest, 'tract', cfg.LATEST_PERIOD)[0]
    return pd.concat(states, ignore_index=True), pd.concat(counties, ignore_index=True), tracts


@pytest.fixture(scope='module')
def pipeline_output():
    return rebuilt()


@pytest.mark.parametrize('index,name', [(0, 'state.csv'), (1, 'counties.csv'), (2, f'tracts_{cfg.LATEST_PERIOD}.csv')])
def test_committed_processed_tables_equal_the_pipeline_output(pipeline_output, index, name):
    pd.testing.assert_frame_equal(read_processed(name), pipeline_output[index], check_dtype=False, rtol=1e-8, atol=1e-8)


def test_the_cleaning_is_deterministic():
    first, second = rebuilt(), rebuilt()
    for a, b in zip(first, second):
        pd.testing.assert_frame_equal(a, b)


def test_a_different_input_gives_a_different_output():
    raw = clean.read_raw('state', cfg.RELEASES[cfg.LATEST_PERIOD])
    changed = raw.copy()
    changed.loc[0, 'B25077_001E'] = changed.loc[0, 'B25077_001E'] + 10000
    a = clean.clean_dataset(raw, 2024, 'state', cfg.LATEST_PERIOD)[0]
    b = clean.clean_dataset(changed, 2024, 'state', cfg.LATEST_PERIOD)[0]
    assert a['home_value'].iloc[0] != b['home_value'].iloc[0]


# ---- keys and geographies -----------------------------------------------------------------------------

def test_counties_cover_67_counties_in_each_of_the_three_periods_once():
    counties = read_processed('counties.csv')
    assert len(counties) == 67 * 3
    assert not counties.duplicated(['geoid', 'period']).any()
    assert set(counties['period']) == set(cfg.RELEASES)
    per_period = [frozenset(g['geoid']) for _, g in counties.groupby('period')]
    assert len(set(per_period)) == 1 and len(per_period[0]) == 67      # the same 67 counties every period
    assert counties['geoid'].str.fullmatch(r'12\d{3}').all()


def test_tracts_are_unique_florida_tracts_with_the_expected_count():
    tracts = read_processed(f'tracts_{cfg.LATEST_PERIOD}.csv')
    assert len(tracts) == 5160 and tracts['geoid'].is_unique
    assert tracts['geoid'].str.fullmatch(r'12\d{9}').all()
    assert set(tracts['geoid'].str[:5]) <= set(read_processed('counties.csv')['geoid'])   # every tract sits in a listed county


def test_state_has_one_row_per_period_and_the_period_table_agrees():
    state = read_processed('state.csv')
    assert state['period'].tolist() == list(cfg.RELEASES) and (state['geoid'] == '12').all()
    assert pd.read_csv(os.path.join(cfg.PROCESSED_DIR, 'periods.csv'))['period'].tolist() == list(cfg.RELEASES)


def test_every_tract_with_housing_units_has_a_boundary_shape():
    shapes = json.load(open(os.path.join(cfg.PROCESSED_DIR, 'florida_tracts.geojson'), encoding='utf-8'))
    ids = {f['properties']['geoid'] for f in shapes['features']}
    tracts = read_processed(f'tracts_{cfg.LATEST_PERIOD}.csv')
    assert tracts.loc[~tracts['geoid'].isin(ids), 'housing_units'].fillna(0).eq(0).all()
    assert len(ids) == 5122 and ids <= set(tracts['geoid'])
