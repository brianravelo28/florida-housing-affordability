# Sources, citations and terms

## Data

| Item | Detail |
|------|--------|
| Source | U.S. Census Bureau, American Community Survey (ACS) 5-year estimates |
| Access | Census Bureau Data API, `https://api.census.gov/data/{year}/acs/acs5` |
| Releases | 2014 (2010-2014), 2019 (2015-2019), 2024 (2020-2024) |
| Tables | B25077 median value; B25064 median gross rent; B19013 median household income; B25070 gross rent as a percentage of household income; B25001 housing units; B25003 tenure |
| Geographies | State (Florida, FIPS 12), 67 counties for all three periods, census tracts for 2020-2024 |
| Retrieved | 2026-11-04 (UTC); exact times and checksums in `data/manifest.json` |
| Cross-check | ACS Data Profile tables DP04 (home value, gross rent) and DP03 (household income), same API |

Suggested citation: U.S. Census Bureau, American Community Survey 5-Year Estimates, tables B25077, B25064, B19013, B25070,
B25001 and B25003, retrieved through the Census Bureau Data API.

## Inflation adjustment

- Census Bureau factors for comparing ACS periods (R-CPI-U-RS): "Comparing 2019 ACS Data" (2014 to 2019 dollars, 1.08096469) and
  "Comparing 2024 ACS Data" (2019 to 2024 dollars, 1.23070782), https://www.census.gov/programs-surveys/acs/guidance/comparing-acs-data.html
- Census Bureau user note "Home Value Estimates in Current Dollars": home value was first adjusted to final-year dollars in the
  2018-2022 5-year release.
- U.S. Bureau of Labor Statistics, Consumer Price Index for All Urban Consumers (CPI-U), U.S. city average, all items,
  1982-84=100, series CUUR0000SA0, annual averages 2010-2024 (BLS Public Data API, retrieved 2026-11-04). Used only to convert the
  2010-2014 and 2015-2019 home values (see [METHODOLOGY.md](METHODOLOGY.md#dollars)).

## Reliability

U.S. Census Bureau, *Understanding and Using American Community Survey Data: What Users of Data for Rural Areas Need to Know*
(2020), chapter 4, section "Assessing ACS Data Reliability": the coefficient of variation (margin of error divided by 1.645,
divided by the estimate) and, in footnote 29, the three bands (under 12% high, 12% to 40% moderate, over 40% low), which it
attributes to Esri, *American Community Survey (ACS): Understanding Margin of Error*,
https://doc.arcgis.com/en/esri-demographics/data/acs.htm. The cutoffs are an Esri guideline that the Census Bureau quotes, not a
Census Bureau standard.

## Boundaries

U.S. Census Bureau, 2024 Cartographic Boundary Files, 1:500,000 (county: `cb_2024_us_county_500k`, Florida tracts:
`cb_2024_12_tract_500k`), https://www.census.gov/geographies/mapping-files.html. The files are simplified for display, are not
legal land descriptions, and are not meant for area or boundary analysis.

## Terms

- **Census Bureau Data API.** The Terms of Service (https://www.census.gov/data/developers/about/terms-of-service.html) require
  apps that use the API to display a notice, which appears on every page of the dashboard and in the README:
  This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.
  The Census Bureau's name is used only to identify the source of the data and never to imply endorsement. The API is provided as
  is, without warranty.
- **Census Bureau data and boundary files.** Works of the U.S. Government are not under copyright protection (17 U.S.C. 105); the
  Census Bureau asks that it be cited as the source.
- **BLS data** is public; the Bureau of Labor Statistics asks for attribution.
- **Code** in this repository is under the MIT license (see `LICENSE`).
