"""
Florida county and census-tract boundaries for the map.

Downloads the Census Bureau's 2024 cartographic boundary files (500k generalization), keeps Florida,
simplifies the shapes for the web and writes small GeoJSON files with only the ID (and county name).
GeoPandas is used here only; the deployed app just reads the GeoJSON.

Counties are the same 67 in every period, so one county file serves the whole timeline. Tracts are the
2020 tracts that the 2020-2024 release uses.
"""

import os
import urllib.request

import geopandas as gpd
import pandas as pd

import acs_config as cfg

BOUNDARY_YEAR = 2024
BASE = f"https://www2.census.gov/geo/tiger/GENZ{BOUNDARY_YEAR}/shp/"
FILES = {
    'tract': f"cb_{BOUNDARY_YEAR}_{cfg.STATE_FIPS}_tract_500k.zip",
    'county': f"cb_{BOUNDARY_YEAR}_us_county_500k.zip",
}
SIMPLIFY_DEGREES = 0.0004  # about 40 m: invisible at statewide zoom, shrinks the file a lot
COORDINATE_DECIMALS = 5    # about 1 m


def download(kind, directory):
    """Download one boundary zip if it isn't already there"""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, FILES[kind])
    if not os.path.exists(path):
        urllib.request.urlretrieve(BASE + FILES[kind], path)
    return path


def prepare(gdf, keep, tolerance=SIMPLIFY_DEGREES):
    """Keep Florida rows and the listed columns, in lon/lat, with simplified shapes"""
    gdf = gdf[gdf['STATEFP'] == cfg.STATE_FIPS].copy()
    gdf = gdf.to_crs(4326)
    gdf['geometry'] = gdf.geometry.simplify(tolerance, preserve_topology=True)
    gdf = gdf.rename(columns={'GEOID': 'geoid', 'NAME': 'name'})
    columns = [c for c in keep if c in gdf.columns]
    return gdf[columns + ['geometry']].sort_values('geoid').reset_index(drop=True)


def write_geojson(gdf, path):
    gdf.to_file(path, driver='GeoJSON', COORDINATE_PRECISION=COORDINATE_DECIMALS)
    return os.path.getsize(path)


def tracts_missing_shapes(tracts, shape_ids):
    """
    Tracts in the data with no boundary shape. Water-only tracts (Census Tract 9900) have no shape and
    no housing units, which is fine; a tract with housing units but no shape would silently vanish from the map.
    Returns (all tract ids without a shape, those of them that have housing units).
    """
    without = tracts[~tracts['geoid'].isin(set(shape_ids))]
    return without['geoid'].tolist(), without.loc[without['housing_units'] > 0, 'geoid'].tolist()


def main():
    boundaries = os.path.join(cfg.RAW_DIR, 'boundaries')
    os.makedirs(cfg.PROCESSED_DIR, exist_ok=True)
    jobs = {'tract': ('florida_tracts.geojson', ['geoid']), 'county': ('florida_counties.geojson', ['geoid', 'name'])}
    for kind, (filename, keep) in jobs.items():
        gdf = prepare(gpd.read_file(download(kind, boundaries)), keep)
        size = write_geojson(gdf, os.path.join(cfg.PROCESSED_DIR, filename))
        print(f"{filename}: {len(gdf):,} shapes, {size / 1e6:.2f} MB")
        if kind == 'tract':
            tracts = pd.read_csv(os.path.join(cfg.PROCESSED_DIR, f'tracts_{cfg.LATEST_PERIOD}.csv'),
                                 dtype={'geoid': str})
            without, with_units = tracts_missing_shapes(tracts, gdf['geoid'])
            print(f"tracts without a shape: {len(without)} (with housing units: {len(with_units)})")
            if with_units:
                raise AssertionError(f"tracts with housing units but no boundary shape: {with_units[:5]}")


if __name__ == '__main__':
    main()
