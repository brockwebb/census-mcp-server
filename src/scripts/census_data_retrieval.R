
# Census Data Retrieval Script
# Called by Python MCP server to fetch ACS data via tidycensus

library(tidycensus)
library(dplyr)
library(jsonlite)

# Parse command line arguments
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
    stop("Usage: Rscript census_data_retrieval.R <location> <variables> <year> <survey>")
}

location_json <- args[1]
variables_json <- args[2]
year <- as.numeric(args[3])
survey <- args[4]

# Parse JSON inputs
location_data <- fromJSON(location_json)
variables_list <- fromJSON(variables_json)

# Set Census API key if available
census_api_key <- Sys.getenv("CENSUS_API_KEY")
if (nchar(census_api_key) > 0) {
    census_api_key(census_api_key)
}

# Main data retrieval function
get_census_data <- function(location_data, variables_list, year, survey) {
    tryCatch({
        # Determine geography type and codes
        geography <- location_data$geography
        state <- location_data$state
        county <- location_data$county
        place <- location_data$place
        
        # Call get_acs based on geography
        if (geography == "state") {
            data <- get_acs(
                geography = "state",
                variables = variables_list,
                year = year,
                survey = survey,
                state = state
            )
        } else if (geography == "county") {
            data <- get_acs(
                geography = "county",
                variables = variables_list,
                year = year,
                survey = survey,
                state = state,
                county = county
            )
        } else if (geography == "place") {
            # Get all places in state, then filter for specific place
            data <- get_acs(
                geography = "place",
                variables = variables_list,
                year = year,
                survey = survey,
                state = state
            )
            
            # Filter for the specific place if specified
            if (!is.null(place) && nchar(place) > 0) {
                # Create search patterns for place matching
                place_patterns <- c(
                    paste0("^", place, "$"),  # Exact match
                    paste0("^", place, ","),  # Place followed by comma
                    paste0(place, " city,"), # City suffix
                    paste0(place, " town,"), # Town suffix
                    paste0(place, " village,") # Village suffix
                )
                
                # Try each pattern until we find a match
                filtered_data <- NULL
                for (pattern in place_patterns) {
                    filtered_data <- data[grepl(pattern, data$NAME, ignore.case = TRUE), ]
                    if (nrow(filtered_data) > 0) {
                        break
                    }
                }
                
                # If no match found, try partial matching
                if (is.null(filtered_data) || nrow(filtered_data) == 0) {
                    # Extract base place name for partial matching
                    base_place <- gsub(" (city|town|village)$", "", place, ignore.case = TRUE)
                    filtered_data <- data[grepl(base_place, data$NAME, ignore.case = TRUE), ]
                }
                
                # Use filtered data if found, otherwise return error
                if (!is.null(filtered_data) && nrow(filtered_data) > 0) {
                    data <- filtered_data
                } else {
                    stop(paste("No data found for place:", place, "in state:", state))
                }
            }
        } else if (geography == "us") {
            data <- get_acs(
                geography = "us",
                variables = variables_list,
                year = year,
                survey = survey
            )
        } else {
            stop(paste("Unsupported geography:", geography))
        }
        
        # Format output
        result <- list(
            data = data,
            source = paste("US Census Bureau American Community Survey", survey, "Estimates"),
            year = year,
            survey = toupper(survey),
            geography = geography,
            success = TRUE
        )
        
        # Convert to JSON and print
        cat(toJSON(result, auto_unbox = TRUE, pretty = TRUE))
        
    }, error = function(e) {
        error_result <- list(
            error = as.character(e),
            success = FALSE
        )
        cat(toJSON(error_result, auto_unbox = TRUE))
    })
}

# Execute main function
get_census_data(location_data, variables_list, year, survey)
