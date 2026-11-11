"""
Florida Housing Affordability: home values, rents and incomes across Florida's counties and census tracts,
from the Census Bureau's American Community Survey (ACS) 5-year estimates, with the margin of error
for every figure.
"""

import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(APP_DIR, 'src'))
import acs_config as cfg  # noqa: E402
import view  # noqa: E402

st.set_page_config(page_title="Florida Housing Affordability", page_icon="🏘️", layout="wide")

st.markdown("""
<style>
html, body, p, span, li, label, input, textarea, select, button, div[class*="css"] { font-size: 17px !important; }
small, [data-testid="stCaptionContainer"], [data-testid="stMetricLabel"] { font-size: 15px !important; }
</style>
""", unsafe_allow_html=True)

PROCESSED = cfg.PROCESSED_DIR
GRAY = '#b0b0b0'
CHART_HINT = "💡 Drag to zoom • Double-click to reset"
MAP_HINT = "💡 Scroll to zoom • Drag to pan • Hover or tap an area for its figure and margin of error"


# ============================================================================
# DATA
# ============================================================================

@st.cache_data
def load_tables():
    read = lambda name: pd.read_csv(os.path.join(PROCESSED, name), dtype={'geoid': str, 'county_fips': str})
    return (read('counties.csv'), read('state.csv'), read(f'tracts_{cfg.LATEST_PERIOD}.csv'),
            pd.read_csv(os.path.join(PROCESSED, 'periods.csv')))


@st.cache_resource
def load_shapes(kind):
    return view.load_geojson(os.path.join(PROCESSED, f'florida_{kind}.geojson'))


try:
    counties, state, tracts, periods = load_tables()
except Exception as e:
    st.error(f"Could not load the data files: {e}\n\nRebuild them with `python run_pipeline.py`.")
    st.stop()

PERIODS = list(periods['period'])
LATEST = cfg.LATEST_PERIOD
county_names = dict(zip(counties.loc[counties['period'] == LATEST, 'geoid'],
                        counties.loc[counties['period'] == LATEST, 'name'].map(view.short_name)))


# ============================================================================
# MAP
# ============================================================================

@st.cache_data(show_spinner="Drawing the map...")
def build_map(geography, metric, period, county_geoid):
    spec = view.METRICS[metric]
    shapes = load_shapes('counties' if geography == 'Counties' else 'tracts')
    shape_ids = {f['properties']['geoid'] for f in shapes['features']}

    if geography == 'Counties':
        frames = [view.map_frame(counties[counties['period'] == p], metric) for p in PERIODS]
        current = view.map_frame(counties[counties['period'] == period], metric)
    else:
        current_all = view.map_frame(tracts, metric)
        frames = [current_all]
        current = current_all
        if county_geoid:
            current = current[current['geoid'].str.startswith(county_geoid)]
    zmin, zmax = view.color_range(frames)  # one scale across all periods (or all of Florida) so maps are comparable
    current = current[current['geoid'].isin(shape_ids)]
    shaded, gray = current[~current['gray']], current[current['gray']]

    fig = go.Figure()
    line = 0.8 if geography == 'Counties' else 0.2
    if len(shaded):
        fig.add_trace(go.Choroplethmap(
            geojson=view.split_geojson(shapes, shaded['geoid']), locations=shaded['geoid'], z=shaded['value'],
            featureidkey='properties.geoid', text=shaded['hover'], hovertemplate='%{text}<extra></extra>',
            colorscale=spec['scale'], zmin=zmin, zmax=zmax, marker_opacity=0.85, marker_line_width=line,
            marker_line_color='white', colorbar=dict(title=spec['unit'], thickness=14, len=0.7)))
    if len(gray):
        fig.add_trace(go.Choroplethmap(
            geojson=view.split_geojson(shapes, gray['geoid']), locations=gray['geoid'], z=[1] * len(gray),
            featureidkey='properties.geoid', text=gray['hover'], hovertemplate='%{text}<extra></extra>',
            colorscale=[[0, GRAY], [1, GRAY]], showscale=False, marker_opacity=0.85, marker_line_width=line,
            marker_line_color='white'))

    if county_geoid and geography == 'Tracts':
        chosen = [f for f in shapes['features'] if f['properties']['geoid'].startswith(county_geoid)]
        (lat, lon), zoom = view.center_and_zoom(chosen)
    else:
        (lat, lon), zoom = (27.9, -83.6), 5.6  # all of Florida
    fig.update_layout(map=dict(style='carto-positron', center=dict(lat=lat, lon=lon), zoom=zoom),
                      margin=dict(l=0, r=0, t=0, b=0), height=640, showlegend=False)
    return fig, current


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("## Explore")
    geography = st.radio("Map level", ["Counties", "Tracts"], horizontal=True,
                         help="Counties: all 67, three time periods. Census tracts: neighborhood-sized areas, "
                              f"for the latest period ({LATEST}).")
    metric = st.selectbox("Measure", list(view.METRICS))
    if geography == 'Counties':
        period = st.select_slider("ACS 5-year period", options=PERIODS, value=LATEST)
    else:
        period = LATEST
        st.caption(f"Tracts use the {LATEST} period.")
    county_geoid = None
    if geography == 'Tracts':
        options = ['All of Florida'] + sorted(county_names.values())
        choice = st.selectbox("Zoom to county", options)
        if choice != 'All of Florida':
            county_geoid = next(g for g, n in county_names.items() if n == choice)
    st.caption("Dollar figures are in 2024 dollars. Each ACS period covers five years of survey responses.")

spec = view.METRICS[metric]

st.markdown("# Florida Housing Affordability")
st.markdown(f"How home values, rents and household incomes compare across Florida's {len(county_names)} counties "
            f"and {len(tracts):,} census tracts, with the margin of error for every figure.")

tab_map, tab_time, tab_about = st.tabs(["🗺️ Map", "📈 County timeline", "ℹ️ About the data"])


def table_view(frame, kind, label):
    """A sortable table of what the map shows"""
    out = pd.DataFrame({
        'Area': frame['name'],
        label: frame['value'],
        'Margin of error (90%)': frame['moe'],
        'CV (%)': frame['cv'],
        'Reliability': [view.band_text(b) if b not in ('ratio', 'component') else '' for b in frame['band']],
        'Shaded on map': ~frame['gray'],
    })
    fmt = {'dollars': '${:,.0f}', 'share': '{:.1f}%', 'ratio': '{:.2f}x'}[kind]
    moe_fmt = '${:,.0f}' if kind == 'dollars' else '{:.1f}'
    st.dataframe(out.style.format({label: fmt, 'Margin of error (90%)': moe_fmt, 'CV (%)': '{:.1f}'}, na_rep='-'),
                 hide_index=True, width='stretch')


def reliability_box():
    st.info(
        "**How reliable is each estimate?** Every figure comes from a survey, so it carries a margin of error "
        "(at 90% confidence). The Census Bureau recommends judging reliability by the coefficient of variation (CV): the "
        "margin of error divided by 1.645, then divided by the estimate. The three bands below come from an Esri report "
        "that the Census Bureau's handbook for rural data users quotes (chapter 4):\n\n"
        "- **Under 12%:** high reliability\n"
        "- **12% to 40%:** moderate reliability\n"
        "- **Over 40%:** low reliability, drawn in **gray**: the margin of error is then about two-thirds of the estimate "
        "or more, so the true value could be anywhere from about a third of the figure to about 1.7 times it\n\n"
        "Areas with no estimate, or an open-ended value (the Census Bureau reports only a limit), are gray too. "
        "The cutoffs are a convention, not a Census Bureau standard. Each area's band appears when you hover over it.")


with tab_map:
    fig, current = build_map(geography, metric, period, county_geoid)
    st.markdown(f"### {metric}, {period}" + (f" ({choice})" if county_geoid else ""))
    st.plotly_chart(fig, width='stretch')
    st.caption(MAP_HINT)

    shaded_n = int((~current['gray']).sum())
    gray_counts = current.loc[current['gray'], 'band'].value_counts()
    area = 'counties' if geography == 'Counties' else 'tracts'
    summary = f"{shaded_n:,} {area} shaded"
    if len(gray_counts):
        parts = []
        labels = {'no_estimate': 'no estimate', 'top_coded': 'open-ended', 'low': 'low reliability',
                  'no_margin': 'no margin of error', 'component': 'with a missing or unreliable median'}
        for band, n in gray_counts.items():
            parts.append(f"{n:,} {labels.get(band, band)}")
        summary += f"; {int(gray_counts.sum()):,} gray ({', '.join(parts)})"
    st.markdown(f"**{summary}.**")
    reliability_box()
    if period != LATEST and spec['col'] in ('home_value', 'value_to_owner_income'):
        st.caption("The Census Bureau did not adjust home values for inflation before its 2018-2022 release, so "
                   f"{period} home values are converted to 2024 dollars with that period's average-year inflation "
                   "factor (accurate to about 1 percentage point).")
    if spec['kind'] == 'ratio':
        st.caption("This ratio divides the median value of owner-occupied homes by the median income of owner households "
                   "(both cover owners only), so it has no margin of error of its own. It is shaded only where both "
                   "medians are reliable.")
    with st.expander("View as table"):
        table_view(current.sort_values('name'), spec['kind'], spec['short'])

with tab_time:
    st.markdown(f"### {metric} by county across ACS periods")
    latest = counties[counties['period'] == LATEST].sort_values('housing_units', ascending=False)
    default = [county_names[g] for g in latest['geoid'].head(3)]
    chosen_names = st.multiselect("Counties to compare", sorted(county_names.values()), default=default)
    name_to_geoid = {n: g for g, n in county_names.items()}
    rows = []
    for p in PERIODS:
        frame = view.map_frame(pd.concat([state[state['period'] == p].assign(name='Florida'),
                                          counties[counties['period'] == p]]), metric)
        for _, r in frame.iterrows():
            if r['name'] == 'Florida' or r['geoid'] in {name_to_geoid[n] for n in chosen_names}:
                rows.append({'Area': r['name'], 'Period': p, 'value': r['value'], 'moe': r['moe']})
    series = pd.DataFrame(rows)
    if series['value'].notna().any():
        fig = px.line(series, x='Period', y='value', color='Area', markers=True,
                      error_y='moe' if series['moe'].notna().any() else None,
                      category_orders={'Period': PERIODS},
                      labels={'value': f"{metric} ({spec['unit']})"})
        fig.update_layout(height=480, font=dict(size=15), margin=dict(t=20))
        st.plotly_chart(fig, width='stretch')
        st.caption(("Whiskers show the margin of error (90%). " if series['moe'].notna().any() else "") + CHART_HINT)
    else:
        st.info("None of the selected areas has a reliable estimate for this measure.")
    st.caption("ACS periods are non-overlapping five-year windows, which the Census Bureau advises for comparisons. "
               "Counties keep the same boundaries across all three.")
    with st.expander("View as table"):
        wide = series.pivot(index='Area', columns='Period', values='value').reindex(columns=PERIODS)
        fmt = {'dollars': '${:,.0f}', 'share': '{:.1f}%', 'ratio': '{:.2f}x'}[spec['kind']]
        st.dataframe(wide.reset_index().style.format({p: fmt for p in PERIODS}, na_rep='-'),
                     hide_index=True, width='stretch')

with tab_about:
    st.markdown("### About the data")
    st.markdown(f"""
- **Source:** the U.S. Census Bureau's American Community Survey (ACS) 5-year estimates, pulled directly from the
  Census Bureau Data API: tables B25077 (median home value), B25064 (median gross rent), B19013 (median household
  income), B25119 (median household income of owners) and B25070 (rent as a share of income).
- **Periods:** {', '.join(PERIODS)}. Each is a five-year window of survey responses, not a single year, and the three
  do not overlap.
- **Geography:** Florida's {len(county_names)} counties for all three periods; {len(tracts):,} census tracts for {LATEST}
  (tracts were redrawn for the 2020 census, so tracts are shown for the latest period only). Water-only areas have no estimate.
- **Dollars:** every dollar figure is in 2024 dollars. Income and rent are converted with the factors the Census Bureau
  publishes. Home values from the 2010-2014 and 2015-2019 releases were not inflation-adjusted by the Census Bureau, so they
  are converted with each period's average-year factor from the Consumer Price Index (accurate to about 1 percentage point).
- **Home value:** the owner's own estimate of what the home would sell for, not a sale price, for owner-occupied homes only.
- **Gross rent:** the contract rent plus the estimated monthly cost of utilities and fuels that the renter pays.
- **Household income:** the income of the householder and everyone else in the household aged 15 or older over the past 12 months.
  "Owner income" is the same measure for households that own their home.
- **Home value to owner income ratio:** median home value divided by the median income of owner households, because home value
  covers owner-occupied homes only. It divides one median by another, so it is a descriptive comparison with no margin of error of
  its own.
- **Renter share:** the share of renter households whose gross rent is 30% or more of their income, among renter households where
  it can be computed (not computed: no rent paid, or no income or a net loss); its margin of error follows the Census Bureau's
  formula for proportions.
- **Reliability:** see the box under the map. Gray areas have no estimate, an open-ended value or low reliability.
- **What it shows:** how housing costs and incomes compare across places and time. It describes where costs are high relative to
  incomes; it does not explain why. Every term is defined in the
  [methodology](https://github.com/brianravelo28/florida-housing-affordability/blob/main/docs/METHODOLOGY.md#terms).
""")
    st.markdown("[Code and methodology on GitHub](https://github.com/brianravelo28/florida-housing-affordability)")

st.markdown("---")
st.caption(view.CENSUS_NOTICE)
