"""
What the dashboard shows: which areas are shaded, which are gray, and what each hover says.
Kept separate from app.py so the rules can be tested without Streamlit.

An area is grayed out (not shaded) when its estimate is missing, top-coded, or low reliability
(CV over 40%); every other area is shaded and its reliability band appears in the hover text.
"""

import json
import math

import numpy as np
import pandas as pd

# The Census Bureau's Terms of Service require this notice wherever the API data is displayed
CENSUS_NOTICE = ("This product uses the Census Bureau Data API but is not endorsed or certified by the "
                 "Census Bureau.")

# Bands whose areas are drawn gray instead of shaded
GRAY_BANDS = frozenset({'low', 'no_estimate', 'top_coded', 'no_margin'})

# Metric label -> how to read its columns. kind: dollars | share | ratio
METRICS = {
    'Median home value': {'col': 'home_value', 'kind': 'dollars', 'scale': 'YlOrRd', 'unit': '2024 dollars',
                          'short': 'Median home value'},
    'Median gross rent (monthly)': {'col': 'rent', 'kind': 'dollars', 'scale': 'YlOrRd', 'unit': '2024 dollars',
                                    'short': 'Median gross rent'},
    'Median household income': {'col': 'income', 'kind': 'dollars', 'scale': 'YlGnBu', 'unit': '2024 dollars',
                                'short': 'Median household income'},
    'Home value to owner income ratio': {'col': 'value_to_owner_income', 'kind': 'ratio', 'scale': 'YlOrRd',
                                         'unit': 'times owner income', 'short': 'Home value / owner income'},
    'Renters paying 30% or more of income on rent': {'col': 'renters_30plus_share', 'kind': 'share', 'scale': 'YlOrRd',
                                                      'unit': '% of renter households', 'short': 'Renters paying 30%+'},
}

BAND_TEXT = {
    'high': 'High reliability',
    'moderate': 'Moderate reliability',
    'low': 'Low reliability',
    'no_estimate': 'No estimate available',
    'top_coded': 'Open-ended (top- or bottom-coded)',
    'no_margin': 'Margin of error not available',
    'not_rated': 'Share is 0% (reliability not defined)',
}

# The reliability bands (an Esri guideline quoted in the Census Bureau's rural-users handbook), spelled out for readers
RELIABILITY_BANDS = [
    ('High reliability', 'CV under 12%', 'shaded'),
    ('Moderate reliability', 'CV 12% to 40%', 'shaded'),
    ('Low reliability', 'CV over 40%', 'gray'),
]


def short_name(name):
    """'Miami-Dade County, Florida' -> 'Miami-Dade County'; 'Census Tract 12.01; Leon County; Florida' -> 'Tract 12.01, Leon County'"""
    name = str(name)
    if name.startswith('Census Tract'):
        tract, county = name.replace('Census Tract', 'Tract').split('; ')[:2]
        return f"{tract}, {county}"
    return name.replace(', Florida', '')


def band_text(band, cv=None):
    text = BAND_TEXT.get(band, str(band))
    if band in ('high', 'moderate', 'low') and cv is not None and pd.notna(cv):
        text += f" (CV {cv:.1f}%)"
    return text


def fmt_value(kind, value):
    if kind == 'dollars':
        return f"${value:,.0f}"
    if kind == 'share':
        return f"{value:.1f}%"
    return f"{value:.1f}x"


def fmt_margin(kind, moe):
    return f"${moe:,.0f}" if kind == 'dollars' else f"{moe:.1f} percentage points"


def _top_code_text(df, col, kind):
    cap, direction = df.get(col + '_top_code_published'), df.get(col + '_open_end')
    if cap is None or direction is None or kind != 'dollars':
        return pd.Series('', index=df.index)
    word = {'above': 'above', 'below': 'below'}
    return pd.Series([f" The Census Bureau reports only that the median is at or {word[d]} ${v:,.0f}."
                      if pd.notna(v) and d in word else '' for v, d in zip(cap, direction)], index=df.index)


def map_frame(df, metric):
    """
    One row per area: geoid, name, value, margin, cv, band, gray (bool), hover text.
    `df` is a cleaned table (counties or tracts) for one period.
    """
    df = df.reset_index(drop=True)  # callers may pass concatenated frames with repeated row labels
    spec = METRICS[metric]
    col, kind = spec['col'], spec['kind']
    out = pd.DataFrame({'geoid': df['geoid'].values, 'name': df['name'].map(short_name).values}, index=df.index)

    if kind == 'ratio':
        parts = {'home value': 'home_value', 'owner income': 'owner_income'}
        bands = {label: df[c + '_band'] for label, c in parts.items()}
        gray = pd.Series(False, index=df.index)
        for b in bands.values():
            gray |= b.isin(GRAY_BANDS)
        out['value'] = df[col].where(~gray)
        out['moe'] = np.nan
        out['cv'] = np.nan
        out['band'] = np.where(gray, 'component', 'ratio')
        hover = []
        for i in df.index:
            if gray[i]:
                why = '; '.join(f"{label}: {band_text(bands[label][i])}" for label in parts
                                if bands[label][i] in GRAY_BANDS)
                hover.append(f"<b>{out.at[i, 'name']}</b><br>Not shaded. {why}")
            else:
                hover.append(
                    f"<b>{out.at[i, 'name']}</b><br>{spec['short']}: {fmt_value(kind, out.at[i, 'value'])}"
                    f"<br>Median home value {fmt_value('dollars', df.at[i, 'home_value'])}: "
                    f"{band_text(bands['home value'][i], df.at[i, 'home_value_cv'])}"
                    f"<br>Median owner-household income {fmt_value('dollars', df.at[i, 'owner_income'])}: "
                    f"{band_text(bands['owner income'][i], df.at[i, 'owner_income_cv'])}"
                    "<br><i>A ratio of two medians; it has no margin of error of its own.</i>")
        out['gray'] = gray
        out['hover'] = hover
        return out

    band = df[col + '_band']
    gray = band.isin(GRAY_BANDS)
    cap_text = _top_code_text(df, col, kind)
    out['value'] = df[col].where(~gray)
    out['moe'] = df[col + '_moe'].where(~gray)
    out['cv'] = df[col + '_cv']
    out['band'] = band.values
    hover = []
    for i in df.index:
        name = out.at[i, 'name']
        if gray[i]:
            hover.append(f"<b>{name}</b><br>Not shaded. {band_text(band[i], out.at[i, 'cv'])}.{cap_text[i]}")
        else:
            moe = out.at[i, 'moe']
            moe_text = f" &plusmn; {fmt_margin(kind, moe)}" if pd.notna(moe) else ''
            hover.append(f"<b>{name}</b><br>{spec['short']}: {fmt_value(kind, out.at[i, 'value'])}{moe_text}"
                         f"<br>{band_text(band[i], out.at[i, 'cv'])}")
    out['gray'] = gray
    out['hover'] = hover
    return out


def color_range(frames, low_pct=2, high_pct=98):
    """Shared color limits from the shaded values of one or more frames (clips outliers so one extreme tract can't wash out the rest)"""
    values = pd.concat([f.loc[~f['gray'], 'value'].dropna() for f in frames])
    if values.empty:
        return 0.0, 1.0
    low, high = np.percentile(values, [low_pct, high_pct])
    return (float(low), float(high)) if high > low else (float(low), float(low) + 1.0)


def split_geojson(geojson, ids):
    """The features whose geoid is in `ids`, as their own FeatureCollection"""
    ids = set(ids)
    return {'type': 'FeatureCollection',
            'features': [f for f in geojson['features'] if f['properties']['geoid'] in ids]}


def _walk(coords):
    if coords and isinstance(coords[0], (int, float)):
        yield coords
    else:
        for c in coords:
            yield from _walk(c)


def center_and_zoom(features, default=((27.9, -83.5), 5.6)):
    """Map center (lat, lon) and zoom that fit the given GeoJSON features"""
    lons, lats = [], []
    for f in features:
        for lon, lat, *_ in _walk(f['geometry']['coordinates']):
            lons.append(lon)
            lats.append(lat)
    if not lons:
        return default
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 1.2)
    zoom = max(3.0, min(11.0, math.log2(280.0 / max(span, 1e-6))))
    return ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2), zoom


def load_geojson(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)
