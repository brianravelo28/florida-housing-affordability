"""
Pull the ACS 5-year tables from the Census Bureau API and save the raw responses.

Raw responses go to data/raw/ (rebuilt by this script, not committed). data/manifest.json records, for
each pull, the release, the endpoint (never the key), the variables, the row count, the retrieval time
and a checksum of the raw file.

The API key is read from the CENSUS_API_KEY environment variable (or a .env file) and is never printed
or written anywhere.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone

import acs_config as cfg

KEY_NAME = 'CENSUS_API_KEY'


def load_key(environ=None, dotenv_path=None):
    """The API key from the environment, falling back to a .env file. Stops with a clear message if unset."""
    environ = os.environ if environ is None else environ
    key = environ.get(KEY_NAME)
    if not key:
        path = dotenv_path or os.path.join(cfg.ROOT, '.env')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for line in f:
                    name, _, value = line.strip().partition('=')
                    if name == KEY_NAME and value:
                        key = value.strip().strip('"').strip("'")
    if not key:
        raise SystemExit(f"{KEY_NAME} is not set. Put your Census API key in the {KEY_NAME} environment "
                         "variable (or in a git-ignored .env file) and run again.")
    return key


def scrub(text, key):
    """Remove the key from any text that might be shown or stored"""
    return text.replace(key, '***') if key else text


def endpoint(api_year):
    return cfg.API_BASE.format(year=api_year)


def geography_params(geography):
    """The 'for' / 'in' parameters for each geography level"""
    if geography == 'state':
        return {'for': f'state:{cfg.STATE_FIPS}'}
    if geography == 'county':
        return {'for': 'county:*', 'in': f'state:{cfg.STATE_FIPS}'}
    if geography == 'tract':
        return {'for': 'tract:*', 'in': f'state:{cfg.STATE_FIPS} county:*'}
    raise ValueError(f"unknown geography: {geography}")


def request_rows(api_year, geography, key, session=None, retries=3):
    """One API call: returns the response as a list of rows (the first row is the header)"""
    import requests
    session = session or requests
    params = {'get': ','.join(['NAME'] + cfg.VARIABLES), **geography_params(geography), 'key': key}
    last = None
    for attempt in range(retries):
        try:
            response = session.get(endpoint(api_year), params=params, timeout=120)
            if response.status_code == 200:
                return response.json()
            last = f"HTTP {response.status_code}: {scrub(response.text[:200], key)}"
        except requests.RequestException as e:
            last = scrub(str(e), key)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Census API request failed for {api_year} {geography}: {last}")


def manifest_entry(period, api_year, geography, rows, raw_path, retrieved_at):
    """A record of one pull. Contains the endpoint but never the key."""
    with open(raw_path, 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return {
        'period': period,
        'api_year': api_year,
        'geography': geography,
        'endpoint': endpoint(api_year),
        'variables': len(cfg.VARIABLES),
        'rows': len(rows) - 1,
        'retrieved_at_utc': retrieved_at,
        'raw_file': os.path.relpath(raw_path, cfg.ROOT).replace('\\', '/'),
        'sha256': digest,
    }


def pulls():
    """What to fetch: state, counties and tracts for every period (tracts only for the latest)"""
    for period, year in cfg.RELEASES.items():
        yield period, year, 'state'
        yield period, year, 'county'
    yield cfg.LATEST_PERIOD, cfg.RELEASES[cfg.LATEST_PERIOD], 'tract'


def main():
    key = load_key()
    os.makedirs(cfg.RAW_DIR, exist_ok=True)
    manifest = []
    for period, year, geography in pulls():
        rows = request_rows(year, geography, key)
        path = os.path.join(cfg.RAW_DIR, f'{geography}_{year}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f)
        retrieved = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        manifest.append(manifest_entry(period, year, geography, rows, path, retrieved))
        print(f"{period} {geography}: {len(rows) - 1:,} rows")
    with open(cfg.MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {cfg.MANIFEST_PATH}")


if __name__ == '__main__':
    main()
