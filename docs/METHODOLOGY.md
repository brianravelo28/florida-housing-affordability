# Methodology

How the data was pulled, cleaned and scored, and what the numbers can and cannot say. Every count below comes from
`data/processed/cleaning_log.json`, which `python run_pipeline.py` writes; a test checks that this page matches it.

## Source and periods

All data comes from the U.S. Census Bureau's American Community Survey (ACS) 5-year estimates, pulled directly from the
Census Bureau Data API (details in [CITATIONS.md](CITATIONS.md)). An ACS 5-year estimate pools five years of survey responses,
so each figure describes a period, not a single year. The three periods used do not overlap, which is what the Census Bureau
advises for comparisons.

| Period | API release year | Tract boundaries |
|--------|------------------|------------------|
| 2010-2014 | 2014 | 2010 |
| 2015-2019 | 2019 | 2010 |
| 2020-2024 | 2024 | 2020 |

Florida's tract count is 4,245 in every release through 2019 and 5,160 from the 2016-2020 release on, so tract boundaries
changed between the second and third period. Counties are the same 67 in all three, which is why the timeline is by county and
the tract map covers 2020-2024 only.

## What is pulled

| Measure | Table | Used as |
|---------|-------|---------|
| Median home value | B25077 | Estimate and margin of error |
| Median gross rent | B25064 | Estimate and margin of error |
| Median household income | B19013 | Estimate and margin of error |
| Rent as a percentage of income | B25070 (total, 30%+ bins, not computed) | Share of renters paying 30% or more |
| Housing units, households, owner and renter households | B25001, B25003 | Counts for context and add-up checks |

Each pull records the endpoint, row count, retrieval time and a checksum of the raw response in `data/manifest.json`
(the API key is never stored).

## Cleaning rules

Each rule is counted. The tract table is the one that needs them; the 67 counties and the state have no special values.

**1. Special values become missing.** The API returns large negative numbers where there is no usable value:
-666666666 (estimate not available), -222222222 (margin of error not available) and -333333333 (margin not applicable because
the median is at the top of the open-ended range). They are converted to missing values and never enter a median, ratio or color.

**2. Top-coded medians are flagged.** When the margin is -333333333 the estimate is only the Census cap (for example
$2,000,001 for home value), so the value is left out and the cap is kept in its own column.

**3. Reliability bands** (next section) are assigned to every estimate.

**4. Dollars** are converted to 2024 dollars (see Dollars).

**5. Derived measures** are the home value to income ratio and the renter share (see Derived measures).

Tracts, 2020-2024 (5,160 tracts):

| Measure | No estimate | Top-coded | High | Moderate | Low |
|---------|-------------|-----------|------|----------|-----|
| Median home value | 190 | 22 | 3,690 | 1,162 | 96 |
| Median gross rent | 397 | 93 | 3,259 | 1,262 | 149 |
| Median household income | 110 | 9 | 2,051 | 2,911 | 79 |
| Renters paying 30%+ of income | 114 | 0 | 319 | 3,500 | 1,138 |

For the renter share, 89 tracts have an estimated share of exactly 0%; their reliability is not defined, so they are shaded.
Home value to income ratio: 4,933 tracts have both medians, and 4,771 have both medians at moderate or high reliability, which
is what the map shades.

Counties: every county has an estimate in every period. Reliability ratings (high / moderate / low):

| Period | Home value | Rent | Income | Renter share |
|--------|------------|------|--------|--------------|
| 2010-2014 | 65 / 2 / 0 | 65 / 2 / 0 | 67 / 0 / 0 | 59 / 7 / 1 |
| 2015-2019 | 65 / 2 / 0 | 66 / 1 / 0 | 67 / 0 / 0 | 59 / 8 / 0 |
| 2020-2024 | 66 / 1 / 0 | 63 / 4 / 0 | 66 / 1 / 0 | 51 / 16 / 0 |

## Reliability

Every estimate has a margin of error at 90% confidence. The coefficient of variation (CV) turns it into a share of the estimate:

CV = (margin of error / 1.645) / estimate

The Census Bureau's ACS handbook (*Understanding and Using American Community Survey Data*) rates estimates by CV:

| CV | Rating | On the map |
|----|--------|-----------|
| Under 12% | High reliability | Shaded |
| 12% to 40% | Moderate reliability | Shaded |
| Over 40% | Low reliability | Gray |

Areas with no estimate, or a top-coded median, are also gray. The 12% and 40% cutoffs are the handbook's convention, not a formal
standard; other Census Bureau papers use other cutoffs (for example 15% and 30%). The same rule is applied to every measure so
the maps are comparable. Each area's rating appears in the hover text and in the table views.

## Dollars

ACS dollar values are adjusted by the Census Bureau to the final year of each period, so periods must be converted to one year's
dollars before they are compared. Everything here is in **2024 dollars**.

- **Income and rent** are converted with the factors the Census Bureau publishes for comparing periods (R-CPI-U-RS):
  1.08096469 from 2014 to 2019 dollars and 1.23070782 from 2019 to 2024 dollars, multiplied for the earliest period (1.330352).
- **Home value** was not inflation-adjusted by the Census Bureau before its 2018-2022 release. The 2010-2014 and 2015-2019 home
  values are therefore raw medians of values reported across the five survey years. Converting them with the final-year factor
  would treat them as final-year dollars and understate them by about 3% to 4% (overstating home value growth by about 6 percentage
  points). They are converted instead with the factor for the average year of the period: the 2024 Consumer Price Index (CPI-U)
  divided by the mean CPI-U of the period's five years, 1.373080 for 2010-2014 and 1.276292 for 2015-2019. The 2020-2024 home values
  are already adjusted and are used as published.
- **How well this works.** The CPI-U annual averages (Bureau of Labor Statistics, series CUUR0000SA0) reproduce the Census Bureau's
  published factors within 0.3%. A second method, converting the Census Bureau's single-year Florida home value medians for each
  survey year separately and averaging, agrees with the average-year factor to within about 1 percentage point. The conversion is
  therefore accurate to about 1 percentage point; this is the one input that does not come from the Census Bureau.

The as-published values are kept in the data (the `*_as_published` columns) so every figure can be traced back to the Census Bureau.

## Derived measures

- **Home value to income ratio:** median home value (owner-occupied homes) divided by median household income. It compares two
  medians for the same area and period, so it has no margin of error of its own; the map shades it only where both medians are
  reliable. It describes places, not the situation of any one household.
- **Renters paying 30% or more of income on rent:** the four 30%+ bins of table B25070 divided by renter households with rent
  computed (the total minus "not computed"). The margin of error follows the Census Bureau's formula for a proportion whose numerator is
  part of its denominator, falling back to its ratio formula when the term under the root is negative.

## Boundaries

County and tract shapes come from the Census Bureau's 2024 cartographic boundary files (1:500,000), simplified to about 40 meters for the
web. They are for display. 5,122 of the 5,160 tracts have a shape; the other 38 are offshore water areas ("Census Tract 9900") with
no housing units and no estimates, and the pipeline fails if a tract with housing units lacks a shape.

## Checks

- Counties add up to the state, and tracts add up to their counties, for every count variable (pipeline fails otherwise).
- No special value survives in any output file.
- Three counties (Miami-Dade, Monroe, Alachua) were checked for home value, rent and income in two periods (2015-2019 and 2020-2024)
  against the Census Bureau's separate Data Profile tables (DP04 and DP03): all 18 values match the as-published figures.
- Offline tests cover each rule: special values, top-coding, reliability bands at their edges, dollar conversion, the margin-of-error
  formula, the add-up checks, and which areas the map shades or grays.

## Limits

- Every figure is a survey estimate. Small areas have wide margins, which is why the dashboard shows the margin and a rating for each.
- A median describes the middle household or home, not the spread.
- ACS periods pool five years, so a figure is not a snapshot of one year, and the overlap rules mean only non-overlapping periods are compared.
- The Census Bureau reports a floor instead of a value for the highest-valued tracts (top-coding), so those are gray.
- Patterns show where and when costs differ; they do not show why.
