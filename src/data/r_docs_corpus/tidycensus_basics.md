# tidycensus Package Basics

## Overview
The tidycensus package provides an interface to US Census Bureau APIs, allowing users to download Census and ACS data directly into R.

## Key Functions

### get_acs()
Retrieves American Community Survey data for specified geographies and variables.

Parameters:
- geography: Geographic level (state, county, place, tract, etc.)
- variables: Census variable codes or table names
- year: ACS year (most recent: 2023)
- survey: "acs1" (1-year) or "acs5" (5-year estimates)
- state: State for sub-state geographies
- county: County for sub-county geographies

### Variable Codes
- B01003_001: Total population
- B19013_001: Median household income
- B25077_001: Median home value
- B17001_002: Population below poverty level

## Best Practices
- Use ACS 5-year estimates for small areas (more reliable)
- Always check margins of error for statistical significance
- Cache API key using census_api_key() function
