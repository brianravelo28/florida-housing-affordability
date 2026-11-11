"""
What the map shows: which areas are shaded or gray, and what the hover says. Uses small cleaned frames.
"""

import pandas as pd
import pytest

import view

SENT_NA, SENT_NO_MOE, SENT_TOP = -666666666, -222222222, -333333333

HIGH = {'B25077_001E': 400000, 'B25077_001M': 16450}      # CV 2.5%
MODERATE = {'B25077_001E': 400000, 'B25077_001M': 131600}  # CV 20%
LOW = {'B25077_001E': 400000, 'B25077_001M': 400000}       # CV about 61%
MISSING = {'B25077_001E': SENT_NA, 'B25077_001M': SENT_NO_MOE}
TOPPED = {'B25077_001E': 2000001, 'B25077_001M': SENT_TOP}


@pytest.fixture
def home_values(make_raw, cleaned):
    return cleaned(make_raw(HIGH, MODERATE, LOW, MISSING, TOPPED))


def test_only_low_missing_and_top_coded_areas_are_gray(home_values):
    frame = view.map_frame(home_values, 'Median home value')
    assert frame['gray'].tolist() == [False, False, True, True, True]
    assert frame['band'].tolist() == ['high', 'moderate', 'low', 'no_estimate', 'top_coded']


def test_gray_areas_carry_no_value_so_they_can_never_set_a_color(home_values):
    frame = view.map_frame(home_values, 'Median home value')
    assert frame.loc[frame['gray'], 'value'].isna().all()
    assert frame.loc[~frame['gray'], 'value'].notna().all()


def test_shaded_hover_shows_the_estimate_margin_and_band(home_values):
    hover = view.map_frame(home_values, 'Median home value')['hover']
    assert '$' in hover[0] and '400,000' in hover[0]
    assert '&plusmn; $16,450' in hover[0]
    assert 'High reliability (CV 2.5%)' in hover[0]
    assert 'Moderate reliability (CV 20.0%)' in hover[1]


def test_gray_hover_explains_why_it_is_not_shaded(home_values):
    hover = view.map_frame(home_values, 'Median home value')['hover']
    assert 'Not shaded' in hover[2] and 'Low reliability' in hover[2]
    assert 'No estimate available' in hover[3]
    assert 'Open-ended' in hover[4] and 'at or above $2,000,001' in hover[4]


def test_ratio_needs_both_medians_to_be_usable(make_raw, cleaned):
    raw = make_raw(
        {**HIGH, 'B25119_002E': 80000, 'B25119_002M': 1000},                      # usable
        {**HIGH, 'B25119_002E': 80000, 'B25119_002M': 80000},                     # owner income unreliable
        {**LOW, 'B25119_002E': 80000, 'B25119_002M': 1000},                       # home value unreliable
    )
    frame = view.map_frame(cleaned(raw), 'Home value to owner income ratio')
    assert frame['gray'].tolist() == [False, True, True]
    assert frame['value'].iloc[0] == pytest.approx(5.0, rel=1e-6)
    assert 'owner income' in frame['hover'].iloc[1].lower() and 'Low reliability' in frame['hover'].iloc[1]
    assert 'no margin of error' in frame['hover'].iloc[0] and 'owner-household income' in frame['hover'].iloc[0]


def test_ratio_does_not_depend_on_all_household_income(make_raw, cleaned):
    raw = make_raw({**HIGH, 'B19013_001E': SENT_NA, 'B19013_001M': SENT_NO_MOE, 'B25119_002E': 100000, 'B25119_002M': 1000})
    frame = view.map_frame(cleaned(raw), 'Home value to owner income ratio')
    assert not frame['gray'].iloc[0] and frame['value'].iloc[0] == pytest.approx(4.0)


def test_bottom_coded_hover_says_below_and_top_coded_says_above(make_raw, cleaned):
    raw = make_raw({'B19013_001E': 2499, 'B19013_001M': SENT_TOP}, {'B19013_001E': 250001, 'B19013_001M': SENT_TOP})
    hover = view.map_frame(cleaned(raw), 'Median household income')['hover']
    assert 'at or below $2,499' in hover.iloc[0]
    assert 'at or above $250,001' in hover.iloc[1]


def test_every_measure_says_how_many_households_the_estimate_covers(make_raw, cleaned):
    raw = make_raw({'B25003_002E': 1234, 'B25003_003E': 567, 'B25003_001E': 1801, 'B25070_001E': 500, 'B25070_011E': 50})
    frame = cleaned(raw)
    expected = {'Median home value': 'Based on about 1,234 owner households',
                'Median gross rent (monthly)': 'Based on about 567 renter households',
                'Median household income': 'Based on about 1,801 households',
                'Home value to owner income ratio': 'Based on about 1,234 owner households',
                'Renters paying 30% or more of income on rent': 'Based on about 450 renter households with rent computed'}
    for metric, text in expected.items():
        assert text in view.map_frame(frame, metric)['hover'].iloc[0], metric


def test_a_household_count_under_30_is_flagged_in_the_hover(make_raw, cleaned):
    hover = view.map_frame(cleaned(make_raw({'B25003_002E': 20})), 'Median home value')['hover'].iloc[0]
    assert 'about 20 owner households (fewer than 30: read with care)' in hover
    assert 'fewer than 30' not in view.map_frame(cleaned(make_raw({'B25003_002E': 30})), 'Median home value')['hover'].iloc[0]


def test_gray_areas_also_show_their_household_count(home_values):
    hover = view.map_frame(home_values, 'Median home value')['hover']
    assert 'Not shaded' in hover[3] and 'Based on about 100 owner households' in hover[3]
    assert view.map_frame(home_values, 'Median home value')['households'].tolist() == [100] * 5


def test_deployment_info_reads_memory_commit_and_versions(tmp_path):
    status = tmp_path / 'status'
    status.write_text('Name:\tpython\nVmRSS:\t  307200 kB\nThreads:\t4\n', encoding='utf-8')
    info = view.deployment_info({'RENDER_GIT_COMMIT': 'abcdef1234567'}, str(status))
    assert info['memory_mb'] == 300.0 and info['commit'] == 'abcdef1'
    assert info['libraries']['pandas'] and info['libraries']['streamlit'] and info['python'].startswith('3.')


def test_deployment_info_copes_with_no_proc_file_and_no_commit(tmp_path):
    info = view.deployment_info({}, str(tmp_path / 'missing'))
    assert info['memory_mb'] is None and info['commit'] is None


def test_share_margin_is_in_percentage_points(make_raw, cleaned):
    raw = make_raw({'B25070_001E': 200, 'B25070_011E': 20, 'B25070_007E': 20, 'B25070_008E': 20,
                    'B25070_009E': 10, 'B25070_010E': 10, 'B25070_007M': 4, 'B25070_008M': 4,
                    'B25070_009M': 4, 'B25070_010M': 4, 'B25070_001M': 6, 'B25070_011M': 8})
    hover = view.map_frame(cleaned(raw), 'Renters paying 30% or more of income on rent')['hover'].iloc[0]
    assert '33.3%' in hover and 'percentage points' in hover


def test_a_share_of_zero_is_still_shaded(make_raw, cleaned):
    raw = make_raw({'B25070_001E': 50, 'B25070_011E': 0, 'B25070_007E': 0, 'B25070_008E': 0,
                    'B25070_009E': 0, 'B25070_010E': 0})
    frame = view.map_frame(cleaned(raw), 'Renters paying 30% or more of income on rent')
    assert frame['band'].iloc[0] == 'not_rated' and not frame['gray'].iloc[0]


def test_frames_with_repeated_row_labels_work(home_values):
    doubled = pd.concat([home_values, home_values])  # e.g. a state row stacked on county rows
    frame = view.map_frame(doubled, 'Median home value')
    assert len(frame) == 10 and frame['gray'].sum() == 6


def test_color_range_ignores_gray_areas_and_clips_outliers():
    values = list(range(100, 200)) + [1_000_000]
    frame = pd.DataFrame({'value': values + [5.0] * 20, 'gray': [False] * 101 + [True] * 20})
    low, high = view.color_range([frame])
    assert 100 <= low < 110 and 190 < high < 300  # the $1,000,000 outlier and the gray 5.0 don't set the limits


def test_color_range_pools_several_frames_and_handles_nothing_to_color():
    a = pd.DataFrame({'value': [10.0, 20.0], 'gray': [False, False]})
    b = pd.DataFrame({'value': [100.0, 200.0], 'gray': [False, False]})
    low, high = view.color_range([a, b])
    assert low < 20 and high > 100
    empty = pd.DataFrame({'value': [float('nan')], 'gray': [True]})
    assert view.color_range([empty]) == (0.0, 1.0)


def test_split_geojson_keeps_only_the_requested_features():
    geo = {'type': 'FeatureCollection', 'features': [
        {'properties': {'geoid': 'a'}}, {'properties': {'geoid': 'b'}}, {'properties': {'geoid': 'c'}}]}
    assert [f['properties']['geoid'] for f in view.split_geojson(geo, ['a', 'c'])['features']] == ['a', 'c']


def feature(x0, y0, x1, y1):
    return {'geometry': {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}


def test_center_and_zoom_fit_the_shapes():
    (lat, lon), zoom = view.center_and_zoom([feature(-82.0, 26.0, -80.0, 28.0)])
    assert (lat, lon) == pytest.approx((27.0, -81.0))
    (_, _), smaller = view.center_and_zoom([feature(-81.1, 27.0, -81.0, 27.1)])
    assert smaller > zoom  # a smaller area zooms in further


def test_center_and_zoom_default_when_there_are_no_shapes():
    assert view.center_and_zoom([]) == ((27.9, -83.5), 5.6)


@pytest.mark.parametrize('name,expected', [
    ('Miami-Dade County, Florida', 'Miami-Dade County'),
    ('Census Tract 12.01; Leon County; Florida', 'Tract 12.01, Leon County'),
    ('Florida', 'Florida'),
])
def test_short_names(name, expected):
    assert view.short_name(name) == expected


def test_reliability_bands_are_spelled_out_for_readers():
    assert view.RELIABILITY_BANDS == [('High reliability', 'CV under 12%', 'shaded'),
                                      ('Moderate reliability', 'CV 12% to 40%', 'shaded'),
                                      ('Low reliability', 'CV over 40%', 'gray')]
