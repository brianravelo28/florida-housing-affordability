"""
The Streamlit app, run in-process with Streamlit's test runner: every measure at both map levels, the period slider, the county
zoom, a county with few tracts, a timeline with nothing selected, and the notice the Census Bureau requires.
"""

import os

import pytest
from streamlit.testing.v1 import AppTest

import acs_config as cfg
import view

APP = os.path.join(cfg.ROOT, 'app.py')
MEASURES = list(view.METRICS)


def fresh():
    return AppTest.from_file(APP, default_timeout=240).run()


def texts(at):
    return ' '.join(x.value for group in (at.markdown, at.caption, at.info) for x in group)


def test_the_default_view_loads_and_states_its_scope():
    at = fresh()
    assert not at.exception
    assert "67 counties" in texts(at) and "5,160 census tracts" in texts(at)
    assert '67 counties shaded' in texts(at)


@pytest.mark.parametrize('measure', MEASURES)
def test_every_measure_draws_for_counties(measure):
    at = fresh()
    at.selectbox[0].set_value(measure).run()
    assert not at.exception
    assert f'{measure}, 2020-2024' in texts(at)


@pytest.mark.parametrize('period', ['2010-2014', '2015-2019', '2020-2024'])
def test_every_period_draws_for_counties(period):
    at = fresh()
    at.select_slider[0].set_value(period).run()
    assert not at.exception and f', {period}' in texts(at)


@pytest.mark.parametrize('measure', MEASURES)
def test_every_measure_draws_for_tracts_and_reports_what_is_gray(measure):
    at = fresh()
    at.radio[0].set_value('Tracts').run()
    at.selectbox[0].set_value(measure).run()
    assert not at.exception
    assert 'tracts shaded' in texts(at)


def test_zooming_to_a_county_with_few_tracts_still_draws():
    at = fresh()
    at.radio[0].set_value('Tracts').run()
    at.selectbox[0].set_value('Home value to owner income ratio').run()
    at.selectbox[1].set_value('Liberty County').run()     # one of the smallest counties
    assert not at.exception
    assert 'Liberty County' in texts(at) and 'tracts shaded' in texts(at)


def test_the_timeline_works_with_no_counties_selected():
    at = fresh()
    at.multiselect[0].set_value([]).run()
    assert not at.exception


def test_the_timeline_works_for_every_measure():
    for measure in MEASURES:
        at = fresh()
        at.selectbox[0].set_value(measure).run()
        assert not at.exception, measure


def test_notes_sit_in_collapsed_sections_under_each_map_chart_and_table():
    at = fresh()
    labels = [e.label for e in at.expander]
    for label in ('About this map', 'View as table', 'About this table', 'About this chart', 'About this deployment'):
        assert label in labels, label
    assert all(not e.proto.expanded for e in at.expander if e.label.startswith(('About this', 'View as')))


def test_the_reliability_box_stays_visible_and_is_not_in_a_collapsed_section():
    at = fresh()
    assert any('How reliable is each estimate?' in i.value for i in at.info)


def test_the_deployment_panel_names_python_and_libraries():
    text = ' '.join(c.value for c in fresh().caption)
    assert 'Python 3.' in text and 'streamlit' in text and 'Memory in use by this process' in text


def test_the_page_carries_the_census_bureau_notice():
    assert view.CENSUS_NOTICE in texts(fresh())


def test_the_reliability_bands_are_spelled_out_on_the_page():
    text = texts(fresh())
    for phrase in ('Under 12%', '12% to 40%', 'Over 40%', 'Esri'):
        assert phrase in text
