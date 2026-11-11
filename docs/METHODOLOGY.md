# Methodology

How the data was pulled, cleaned and scored, and what the numbers can and cannot say. Every count below comes from
`data/processed/cleaning_log.json`, which `python run_pipeline.py` writes; a test checks that this page matches it.

Contents: [Terms](#terms) · [Source and periods](#source-and-periods) · [What is pulled](#what-is-pulled) · [Cleaning rules](#cleaning-rules) · [Reliability](#reliability) · [Dollars](#dollars) · [Derived measures](#derived-measures) · [Boundaries](#boundaries) · [Checks](#checks) · [Limits](#limits)

## Terms

| Term | Meaning |
|------|---------|
| ACS 5-year estimate | An estimate from the Census Bureau's American Community Survey that pools five years of survey responses. It describes a period, not a single year. |
| Period | A non-overlapping five-year window: 2010-2014, 2015-2019 or 2020-2024. |
| Margin of error | The Census Bureau's margin around an estimate, at 90% confidence. |
| Coefficient of variation (CV) | The margin of error divided by 1.645, then divided by the estimate (see [Reliability](#reliability)). |
| Reliability band | High (CV under 12%), moderate (12% to 40%) or low (over 40%); the source of the cutoffs is in [Reliability](#reliability). |
| Gray area | An area the map does not shade: no estimate, an open-ended value, or low reliability. |
| Median home value | The middle value of owner-occupied homes (table B25077). Each value is the owner's own answer to how much the home (house and lot, apartment or mobile home) would sell for if it were for sale. It is the owner's estimate, not a sale price, and it covers only homes that their owners live in. |
| Median gross rent | The middle monthly gross rent of rented homes where rent is paid (B25064). Gross rent is the contract rent plus the estimated monthly cost of the utilities and fuels the renter pays. |
| Median household income | The middle annual income of all households (B19013), owners and renters together. A household's income is the income of the householder and everyone else in the household aged 15 or older, over the past 12 months, in inflation-adjusted dollars. |
| Median owner-household income | The same measure for households that own their home (B25119, median household income by tenure). |
| Home value to owner income ratio | Median home value divided by median owner-household income. Both cover owner households only. |
| Gross rent as a percentage of household income | For each renter household, its monthly gross rent divided by its monthly income (B25070). It is not computed for households that pay no rent or that report no income or a net loss. |
| Renters paying 30% or more | Renter households whose gross rent is 30% or more of their income, as a share of the renter households where the percentage can be computed. |
| Open-ended value | A median in the lowest or highest interval of the Census Bureau's range, so only the limit is reported (for example "250,000+" for income and "2,000,000+" for home value; the lowest income interval is "2,500-"). Also called top-coded or bottom-coded. |
| 2024 dollars | Dollar figures adjusted for inflation to 2024 (see [Dollars](#dollars)). |
| Census tract | A neighborhood-sized area drawn by the Census Bureau; Florida has 5,160 in the 2020 boundaries. |

## Source and periods

All data comes from the U.S. Census Bureau's American Community Survey (ACS) 5-year estimates, pulled directly from the
Census Bureau Data API (details in [CITATIONS.md](CITATIONS.md)). The three periods do not overlap, which is what the Census
Bureau advises for comparisons.

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
| Median owner-household income | B25119 (owner occupied) | Estimate and margin of error; the denominator of the home value ratio |
| Rent as a percentage of income | B25070 (total, 30%+ bins, not computed) | Share of renters paying 30% or more |
| Housing units, households, owner and renter households | B25001, B25003 | Counts for context and add-up checks |

Each pull records the endpoint, row count, retrieval time and a checksum of the raw response in `data/manifest.json`
(the API key is never stored).

## Cleaning rules

Each rule is counted. The tract table is the one that needs them; the 67 counties and the state have no special values.

**1. Special values become missing.** The API returns large negative numbers where there is no usable value:
-666666666 (the estimate could not be computed), -222222222 (the margin of error could not be computed) and -333333333 (the
margin of error could not be computed because the median falls in the lowest or highest interval of an open-ended range). They are
converted to missing values and never enter a median, ratio or color.

**2. Open-ended medians are flagged.** When the margin is -333333333 the reported estimate is only the limit of the open-ended
interval (for example $2,000,001 for home value, or $2,499 for the lowest income interval), so the value is left out. The limit is
kept in its own column, with whether it is a top or a bottom limit.

**3. Reliability bands** (next section) are assigned to every estimate.

**4. Dollars** are converted to 2024 dollars (see Dollars).

**5. Derived measures** are the home value to owner income ratio and the renter share (see Derived measures).

Tracts, 2020-2024 (5,160 tracts):

| Measure | No estimate | Open-ended | High | Moderate | Low |
|---------|-------------|------------|------|----------|-----|
| Median home value | 190 | 22 | 3,690 | 1,162 | 96 |
| Median gross rent | 397 | 93 | 3,259 | 1,262 | 149 |
| Median household income | 110 | 9 | 2,051 | 2,911 | 79 |
| Median owner-household income | 260 | 24 | 1,729 | 2,918 | 229 |
| Renters paying 30%+ of income | 114 | 0 | 319 | 3,500 | 1,138 |

Two of the 24 open-ended owner-income tracts are bottom-coded (the median is in the lowest interval); every other open-ended
median is top-coded. For the renter share, 89 tracts have an estimated share of exactly 0%; their reliability is not defined, so they
are shaded. Home value to owner income ratio: 4,823 tracts have both medians, and 4,532 have both medians at moderate or high
reliability, which is what the map shades.

Counties: every county has an estimate in every period. Reliability ratings (high / moderate / low):

| Period | Home value | Rent | Income | Owner income | Renter share |
|--------|------------|------|--------|--------------|--------------|
| 2010-2014 | 65 / 2 / 0 | 65 / 2 / 0 | 67 / 0 / 0 | 65 / 2 / 0 | 59 / 7 / 1 |
| 2015-2019 | 65 / 2 / 0 | 66 / 1 / 0 | 67 / 0 / 0 | 67 / 0 / 0 | 59 / 8 / 0 |
| 2020-2024 | 66 / 1 / 0 | 63 / 4 / 0 | 66 / 1 / 0 | 67 / 0 / 0 | 51 / 16 / 0 |

## Reliability

Every estimate has a margin of error at 90% confidence. The coefficient of variation (CV) turns it into a share of the estimate:

CV = (margin of error / 1.645) / estimate

The Census Bureau recommends the CV as the measure of an estimate's reliability. Its handbook for rural data users
(*Understanding and Using American Community Survey Data: What Users of Data for Rural Areas Need to Know*, chapter 4, "Assessing
ACS Data Reliability") applies three bands that, in its words, a 2014 report from Esri proposes (footnote 29):

| CV | Rating | On the map |
|----|--------|-----------|
| Under 12% | High reliability | Shaded |
| 12% to 40% | Moderate reliability | Shaded |
| Over 40% | Low reliability | Gray |

The 12% and 40% cutoffs are therefore an Esri guideline that the Census Bureau quotes, a convention and not a Census Bureau
standard. At a CV of 40% the 90% margin of error is 1.645 x 0.40, about 66% of the estimate, so the true value could plausibly be
anywhere from about a third of the figure to about 1.7 times it; the map does not shade an estimate that uncertain. Areas with no
estimate, or an open-ended median, are also gray. The same rule is applied to every measure so the maps are comparable. Each area's
rating appears in the hover text and in the table views.

## Dollars

ACS dollar values are adjusted by the Census Bureau to the final year of each period, so periods must be converted to one year's
dollars before they are compared. Everything here is in **2024 dollars**.

- **Income and rent** are converted with the factors the Census Bureau publishes for comparing periods (R-CPI-U-RS):
  1.08096469 from 2014 to 2019 dollars and 1.23070782 from 2019 to 2024 dollars, multiplied for the earliest period (1.330352).
- **Home value** was not inflation-adjusted by the Census Bureau before its 2018-2022 release. The 2010-2014 and 2015-2019 home
  values are therefore raw medians of values reported across the five survey years, each in the dollars of the year it was reported.
  They are converted with the factor for the average year of the period: the 2024 Consumer Price Index (CPI-U) divided by the mean
  CPI-U of the period's five years, 1.373080 for 2010-2014 and 1.276292 for 2015-2019. The 2020-2024 home values are already
  adjusted and are used as published.

**Checking the home value conversion.** The conversion is the one input that does not come from the Census Bureau, so
`src/home_value_conversion_check.py` writes `data/processed/home_value_conversion_check.csv` (Florida, 2024 dollars), the only
source of the figures below:

| | 2010-2014 | 2015-2019 |
|---|-----------|-----------|
| Published median (not inflation-adjusted) | $156,200 | $215,300 |
| Converted with the average-year factor (used; factor in parentheses) | $214,475 (1.3731) | $274,786 (1.2763) |
| Converted with the final-year factor, Census Bureau factor | $207,801 (1.3304) | $264,971 (1.2307) |
| Converted with the final-year factor, CPI-U ratio | $206,974 (1.3251) | $264,171 (1.2270) |
| Understatement by the final-year factor (Census Bureau factor / CPI-U) | 3.2% / 3.6% | 3.7% / 4.0% |
| Growth to 2020-2024 ($359,000): average-year factor | +67.4% | +30.6% |
| Growth to 2020-2024: final-year factor (Census Bureau factor / CPI-U) | +72.8% / +73.5% | +35.5% / +35.9% |
| Overstatement of growth by the final-year factor, percentage points | 5.4 / 6.1 | 4.8 / 5.2 |
| Second method: single-year medians, each converted with its own year's CPI-U, averaged | $214,257 | $271,805 |
| Difference from the average-year conversion | -0.1% | -1.1% |
| Growth by the second method (difference from the average-year growth, points) | +67.6% (0.2) | +32.1% (1.4) |

Converting with the final-year factor would treat the values as final-year dollars: it understates them by 3.2% to 4.0% and
overstates growth to 2020-2024 by 4.8 to 6.1 percentage points (the ranges cover the two factor bases). The second method uses the
Census Bureau's single-year Florida medians for 2010-2019 (`data/home_value_1year_medians.csv`); it assumes a five-year median is
close to the average of the yearly medians, which is approximate, and it is a state-level check only. It differs from the
average-year conversion by 0.1% and 1.1% in value. The CPI-U annual averages (Bureau of Labor Statistics, series CUUR0000SA0) give
final-year factors within 0.4% (2010-2014) and 0.3% (2015-2019) of the chained factors the Census Bureau publishes. The conversion
is therefore good to about 1% in the converted value.

The as-published values are kept in the data (the `*_as_published` columns) so every figure can be traced back to the Census Bureau.

## Derived measures

- **Home value to owner income ratio:** median home value divided by median owner-household income. Home value covers
  owner-occupied homes only, so the denominator is the income of owner households, not of all households: owners earn more than
  renters, and dividing by all households would compare two different groups. With the median income of all households the ratio
  would be 3.4, 4.0, 4.8 for the three periods instead of 2.8, 3.3, 4.1. It compares two medians for the same area and period, so
  the map shows no margin of error for it and shades it only where both medians are reliable. It describes places, not the
  situation of any one household.
- **Comparing ratios.** To say whether two counties' ratios, or one county's ratio in two periods, differ, an approximate 90% margin
  is computed with the Census Bureau's formula for a ratio, sqrt(margin of the value^2 + ratio^2 x margin of the income^2) divided
  by the income. Two ratios are treated as different only when they differ by more than the square root of the sum of their squared
  margins. The formula assumes the two medians are independent; they come from the same survey, so this is an approximation. It
  gives the README's statements that the ratio rose in 63 of 67 counties and by more than its margin in 53 (and fell, by less than
  its margin, in four), that Monroe and Collier are clearly above every other county, and that the next three, and the lowest three,
  cannot be told apart. Tests fail if any of these stops being true.
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
  against the Census Bureau's separate Data Profile tables (DP04 and DP03): all 18 values match the as-published figures
  (`data/processed/profile_crosscheck.csv`, written by `src/crosscheck_profile.py`).
- Offline tests cover each rule: special values, open-ended values (top and bottom), reliability bands at their edges, dollar
  conversion, the margin-of-error formula, the add-up checks, which denominator the ratio uses, and which areas the map shades or grays.

## Limits

- Every figure is a survey estimate. Small areas have wide margins, which is why the dashboard shows the margin and a rating for each.
- A median describes the middle household or home, not the spread.
- ACS periods pool five years, so a figure is not a snapshot of one year, and the overlap rules mean only non-overlapping periods are compared.
- The Census Bureau reports only a limit for medians in the open-ended intervals (for example the highest-valued tracts), so those are gray.
- Differences between areas or periods are called real only when they exceed the combined margin of error.
- Patterns show where and when costs differ; they do not show why.
