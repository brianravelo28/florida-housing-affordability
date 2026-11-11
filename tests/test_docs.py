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


def test_methodology_conversion_table_matches_the_committed_check():
    import pandas as pd
    doc = re.sub(r'\s+', ' ', read('docs', 'METHODOLOGY.md'))
    check = pd.read_csv(cfg.CONVERSION_CHECK_PATH)
    expected = []
    for _, r in check.iterrows():
        expected += [f"${r.published_median:,.0f}", f"${r.converted_average_year:,.0f}", f"({r.factor_average_year:.4f}",
                     f"${r.converted_final_year_census:,.0f}", f"${r.converted_final_year_cpi:,.0f}",
                     f"${r.converted_yearly_medians:,.0f}",
                     f"{r.understatement_pct_census:.1f}% / {r.understatement_pct_cpi:.1f}%",
                     f"+{r.growth_pct_average_year:.1f}%",
                     f"+{r.growth_pct_final_year_census:.1f}% / +{r.growth_pct_final_year_cpi:.1f}%",
                     f"{r.growth_overstatement_points_census:.1f} / {r.growth_overstatement_points_cpi:.1f}",
                     f"{r.method_gap_pct:.1f}%", f"+{r.growth_pct_yearly_medians:.1f}% ({r.method_gap_growth_points:.1f})"]
    under = check[['understatement_pct_census', 'understatement_pct_cpi']].to_numpy()
    over = check[['growth_overstatement_points_census', 'growth_overstatement_points_cpi']].to_numpy()
    expected += [f"understates them by {under.min():.1f}% to {under.max():.1f}%",
                 f"overstates growth to 2020-2024 by {over.min():.1f} to {over.max():.1f} percentage points",
                 f"by {abs(check.method_gap_pct[0]):.1f}% and {abs(check.method_gap_pct[1]):.1f}% in value",
                 f"within {abs(check.cpi_vs_census_factor_pct[0]):.1f}% (2010-2014) and {abs(check.cpi_vs_census_factor_pct[1]):.1f}% (2015-2019)"]
    missing = [e for e in expected if e not in doc]
    assert not missing, f"Methodology differs from home_value_conversion_check.csv: {missing}"


def test_methodology_names_the_check_scripts_and_the_cross_check_result():
    import pandas as pd
    doc = read('docs', 'METHODOLOGY.md')
    result = pd.read_csv(cfg.PROFILE_CHECK_PATH)
    assert f"all {len(result)} values match" in doc and result['match'].all()
    for name in ('home_value_conversion_check.py', 'home_value_conversion_check.csv', 'crosscheck_profile.py', 'profile_crosscheck.csv'):
        assert name in doc, name


def test_methodology_tract_exclusions_match_what_the_map_shows():
    import pandas as pd
    doc = re.sub(r'\s+', ' ', read('docs', 'METHODOLOGY.md'))
    tracts = pd.read_csv(os.path.join(cfg.PROCESSED_DIR, f'tracts_{cfg.LATEST_PERIOD}.csv'), dtype={'geoid': str})
    shapes = json.load(open(os.path.join(cfg.PROCESSED_DIR, 'florida_tracts.geojson'), encoding='utf-8'))
    mapped = tracts[tracts['geoid'].isin({f['properties']['geoid'] for f in shapes['features']})]
    assert f"| Census tracts in Florida (2020 boundaries), 2020-2024 release | {len(tracts):,} |" in doc
    assert f"| Tracts on the map | {len(mapped):,} |" in doc and f"| {len(tracts) - len(mapped)} |" in doc
    labels = {'Median home value': 'Median home value', 'Median gross rent (monthly)': 'Median gross rent',
              'Median household income': 'Median household income', 'Renters paying 30% or more of income on rent': 'Renters paying 30%+ of income'}
    for metric, label in labels.items():
        frame = view.map_frame(mapped, metric)
        bands = frame.loc[frame['gray'], 'band'].value_counts()
        row = (f"| {label} | {len(frame):,} | {int((~frame['gray']).sum()):,} | {int(bands.get('no_estimate', 0)):,} | "
               f"{int(bands.get('top_coded', 0)):,} | {int(bands.get('low', 0)):,} |")
        assert row in doc, row
    ratio = view.map_frame(mapped, 'Home value to owner income ratio')
    assert f"| Home value to owner income ratio | {len(ratio):,} | {int((~ratio['gray']).sum()):,} | {int(ratio['gray'].sum()):,} (" in doc


def test_methodology_checksums_and_pull_date_match_the_manifest():
    doc = read('docs', 'METHODOLOGY.md')
    manifest = json.load(open(cfg.MANIFEST_PATH, encoding='utf-8'))
    for entry in manifest:
        assert f"`{entry['sha256'][:16]}`" in doc and entry['raw_file'] in doc
    assert f"pulled {manifest[0]['retrieved_at_utc'][:10]} (UTC)" in doc
    assert manifest[0]['retrieved_at_utc'][:10] in read('docs', 'CITATIONS.md')


def test_the_host_health_check_is_streamlits_real_endpoint_and_documented():
    assert 'healthCheckPath: /_stcore/health' in read('render.yaml')
    assert '/_stcore/health' in read('docs', 'METHODOLOGY.md') and '/_stcore/health' in read('docs', 'DEPLOYMENT.md')


def test_methodology_has_the_standard_sections():
    doc = read('docs', 'METHODOLOGY.md')
    for heading in ('## Terms', '## Data sources', '## Cleaning rules', '## Reproducibility', '## Deployment notes'):
        assert heading in doc, heading
    contents = doc.split('Contents:')[1].split('\n')[0]
    for anchor in ('#terms', '#data-sources', '#reproducibility', '#deployment-notes'):
        assert anchor in contents, anchor


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
