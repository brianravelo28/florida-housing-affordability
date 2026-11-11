"""
The documentation must match the files it describes: the cleaning counts in METHODOLOGY.md come from
cleaning_log.json, the Census Bureau's required notice is on the page, and the manifest holds no secrets.
"""

import json
import os
import re

import acs_config as cfg
import view

ROOT = cfg.ROOT


def read(*parts):
    return open(os.path.join(ROOT, *parts), encoding='utf-8').read()


def log():
    return json.load(open(os.path.join(cfg.PROCESSED_DIR, 'cleaning_log.json'), encoding='utf-8'))


def test_methodology_tract_table_matches_the_cleaning_log():
    doc, tracts = read('docs', 'METHODOLOGY.md'), log()['2020-2024 tracts']
    rows = {
        'Median home value': tracts['home_value'], 'Median gross rent': tracts['rent'],
        'Median household income': tracts['income'], 'Median owner-household income': tracts['owner_income'],
        'Renters paying 30%+ of income': tracts['renters_30plus_share'],
    }
    for label, counts in rows.items():
        expected = [counts['no_estimate'], counts.get('top_coded', 0), counts['band_high'],
                    counts['band_moderate'], counts['band_low']]
        line = next(l for l in doc.splitlines() if l.startswith(f'| {label}') and re.search(r'\|\s*\d', l))
        cells = [int(c.replace(',', '')) for c in re.findall(r'\|\s*([\d,]+)\s*(?=\|)', line)]
        assert cells == expected, (label, cells, expected)


def test_methodology_county_table_matches_the_cleaning_log():
    doc, data = read('docs', 'METHODOLOGY.md'), log()
    for period in cfg.RELEASES:
        counties = data[f'{period} counties']
        expected = ' | '.join(
            ' / '.join(str(counties[m][f'band_{b}']) for b in ('high', 'moderate', 'low'))
            for m in ('home_value', 'rent', 'income', 'owner_income', 'renters_30plus_share'))
        line = next(l for l in doc.splitlines() if l.startswith(f'| {period} | ') and ' / ' in l)
        assert ' | '.join(c.strip() for c in line.strip('|').split('|')[1:]) == expected


def test_methodology_ratio_and_shape_counts_match():
    doc, tracts = read('docs', 'METHODOLOGY.md'), log()['2020-2024 tracts']
    assert f"{tracts['value_to_owner_income']['computed']:,} tracts have both medians" in doc
    assert f"{tracts['renters_30plus_share']['share_is_zero']} tracts have an estimated share of exactly 0%" in doc


def test_methodology_quotes_the_ratio_counts_and_the_all_households_sensitivity():
    import findings
    doc = re.sub(r'\s+', ' ', read('docs', 'METHODOLOGY.md'))  # ignore line breaks in the page
    f = findings.compute(*findings.read_tables())
    assert f"{f['tracts_with_ratio']:,} have both medians at moderate or high reliability" in doc
    sens = ", ".join(f"{f[f'ratio_all_households_{t}']:.1f}" for t in ('first', 'mid', 'last'))
    own = ", ".join(f"{f[f'ratio_{t}']:.1f}" for t in ('first', 'mid', 'last'))
    assert f"{sens}" in doc and f"{own}" in doc


def test_the_census_notice_is_on_every_surface_that_needs_it():
    notice = 'This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.'
    assert view.CENSUS_NOTICE == notice
    assert notice in read('README.md')
    assert notice in read('docs', 'CITATIONS.md')
    assert 'st.caption(view.CENSUS_NOTICE)' in read('app.py')  # shown at the bottom of every page


def test_manifest_stores_endpoints_and_checksums_but_no_key_parameter():
    manifest = json.load(open(cfg.MANIFEST_PATH, encoding='utf-8'))
    assert len(manifest) == 7
    text = json.dumps(manifest).lower()
    assert 'key=' not in text and 'api_key' not in text
    assert all(len(m['sha256']) == 64 and m['endpoint'].startswith('https://api.census.gov/') for m in manifest)


def test_the_readme_python_badge_matches_the_pinned_version():
    assert read('.python-version').startswith('3.14')
    assert 'python-3.14' in read('README.md')
