"""
Fetching (with a fake session, no network) and boundary preparation (tiny hand-made shapes).
"""

import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

import acs_config as cfg
import fetch_acs
import geometry

KEY = 'abc123SECRETKEY'


# ---- the API key ---------------------------------------------------------------------------------------

def test_key_is_read_from_the_environment():
    assert fetch_acs.load_key({'CENSUS_API_KEY': KEY}, dotenv_path='nonexistent.env') == KEY


def test_missing_key_stops_with_a_clear_message_that_names_the_variable(tmp_path):
    with pytest.raises(SystemExit) as stopped:
        fetch_acs.load_key({}, dotenv_path=str(tmp_path / 'missing.env'))
    assert 'CENSUS_API_KEY' in str(stopped.value)


def test_key_can_come_from_a_dotenv_file(tmp_path):
    env = tmp_path / '.env'
    env.write_text('OTHER=1\nCENSUS_API_KEY="' + KEY + '"\n', encoding='utf-8')
    assert fetch_acs.load_key({}, dotenv_path=str(env)) == KEY


def test_scrub_removes_the_key():
    assert KEY not in fetch_acs.scrub(f'GET ...?key={KEY} failed', KEY)


# ---- requests and manifest -----------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status, payload=None, text=''):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fetch_acs.time, 'sleep', lambda s: None)


def test_request_asks_for_every_variable_and_the_right_geography():
    session = FakeSession([FakeResponse(200, [['NAME'], ['x']])])
    rows = fetch_acs.request_rows(2024, 'tract', KEY, session=session)
    url, params = session.calls[0]
    assert rows == [['NAME'], ['x']]
    assert url == 'https://api.census.gov/data/2024/acs/acs5'
    assert params['get'].split(',')[0] == 'NAME' and len(params['get'].split(',')) == 1 + len(cfg.VARIABLES)
    assert params['for'] == 'tract:*' and params['in'] == 'state:12 county:*'


def test_request_retries_then_succeeds():
    session = FakeSession([FakeResponse(500, text='oops'), FakeResponse(200, [['NAME'], ['x']])])
    assert fetch_acs.request_rows(2014, 'county', KEY, session=session) == [['NAME'], ['x']]
    assert len(session.calls) == 2


def test_a_successful_response_with_no_data_rows_is_a_failure():
    """The API can answer 200 and return only the header (or an empty body); that must not pass as data"""
    for body in ([['NAME']], [], {'error': 'nothing'}):
        session = FakeSession([FakeResponse(200, body)] * 3)
        with pytest.raises(RuntimeError) as failed:
            fetch_acs.request_rows(2014, 'county', KEY, session=session)
        assert 'no data rows' in str(failed.value)


def test_failed_request_raises_without_leaking_the_key():
    session = FakeSession([FakeResponse(401, text=f'invalid key {KEY}')] * 3)
    with pytest.raises(RuntimeError) as failed:
        fetch_acs.request_rows(2014, 'state', KEY, session=session)
    assert KEY not in str(failed.value)


def test_manifest_entry_has_the_endpoint_and_checksum_but_not_the_key(tmp_path):
    raw = tmp_path / 'county_2019.json'
    raw.write_text(json.dumps([['NAME'], ['a'], ['b']]), encoding='utf-8')
    entry = fetch_acs.manifest_entry('2015-2019', 2019, 'county', [['NAME'], ['a'], ['b']], str(raw), '2026-11-03T00:00:00Z')
    assert entry['rows'] == 2 and entry['endpoint'].endswith('/2019/acs/acs5')
    assert len(entry['sha256']) == 64
    assert KEY not in json.dumps(entry)


def test_what_gets_pulled():
    pulled = list(fetch_acs.pulls())
    assert [p for p in pulled if p[2] == 'tract'] == [('2020-2024', 2024, 'tract')]
    assert sorted({p[0] for p in pulled}) == sorted(cfg.RELEASES)
    assert len(pulled) == 3 * 2 + 1


# ---- boundaries ----------------------------------------------------------------------------------------

def square(x, y, size=0.01):
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


def test_prepare_keeps_only_florida_in_lon_lat_with_ids_sorted():
    gdf = gpd.GeoDataFrame({'STATEFP': ['12', '13', '12'], 'GEOID': ['12003', '13001', '12001'],
                            'NAME': ['B', 'Other', 'A'],
                            'geometry': [square(-82, 29), square(-84, 33), square(-81, 28)]}, crs=4269)
    out = geometry.prepare(gdf, ['geoid', 'name'])
    assert out['geoid'].tolist() == ['12001', '12003'] and out['name'].tolist() == ['A', 'B']
    assert out.crs.to_epsg() == 4326
    assert list(out.columns) == ['geoid', 'name', 'geometry']


def test_prepare_simplifies_without_dropping_shapes():
    wiggly = Polygon([(0, 0), (0.005, 0.00001), (0.01, 0), (0.01, 0.01), (0, 0.01)])
    gdf = gpd.GeoDataFrame({'STATEFP': ['12'], 'GEOID': ['12001'], 'geometry': [wiggly]}, crs=4269)
    out = geometry.prepare(gdf, ['geoid'], tolerance=0.001)
    assert len(out) == 1 and len(out.geometry.iloc[0].exterior.coords) < len(wiggly.exterior.coords)


def test_tracts_without_shapes_are_reported_and_units_matter():
    tracts = pd.DataFrame({'geoid': ['1', '2', '3'], 'housing_units': [10, 0, 5]})
    without, with_units = geometry.tracts_missing_shapes(tracts, ['1'])
    assert without == ['2', '3'] and with_units == ['3']
