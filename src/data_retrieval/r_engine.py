"""
R Data Retrieval Engine for Census MCP Server

Handles subprocess calls to R tidycensus for Census data retrieval.
Manages geography parsing, variable mapping, and statistical validation.
"""

import asyncio
import json
import logging
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import os

from utils.config import get_config

logger = logging.getLogger(__name__)

class RDataRetrieval:
    """
    R subprocess interface for Census data retrieval via tidycensus.
    
    Handles:
    - Geography parsing (location names → R geography parameters)
    - Variable mapping (concepts → Census variable codes)  
    - R subprocess execution with proper error handling
    - Statistical validation and MOE handling
    """
    
    def __init__(self, r_script_path: Optional[Path] = None):
        """Initialize R data retrieval engine."""
        self.config = get_config()
        self.r_script_path = r_script_path or self.config.r_script_path
        
        # Ensure R script exists
        self._ensure_r_script()
        
        # Initialize variable mappings (expandable)
        self._init_variable_mappings()
        
        # Initialize geography patterns
        self._init_geography_patterns()
        
        logger.info("R Data Retrieval Engine initialized")
    
    def _ensure_r_script(self):
        """Ensure R script exists, create if needed."""
        if not self.r_script_path.exists():
            logger.info("Creating R script for Census data retrieval")
            success = self.config.save_r_script()
            if not success:
                raise RuntimeError("Failed to create R script")
    
    def _init_variable_mappings(self):
        """Initialize common variable mappings (expandable via config)."""
        # Basic ACS variables - can be loaded from config/knowledge base later
        self.variable_mappings = {
            # Population
            "population": "B01003_001",
            "total_population": "B01003_001",
            "pop": "B01003_001",
            
            # Income
            "median_income": "B19013_001",
            "median_household_income": "B19013_001",
            "household_income": "B19013_001",
            "income": "B19013_001",
            
            # Poverty
            "poverty_rate": "B17001_002",  # Below poverty level
            "poverty": "B17001_002",
            "below_poverty": "B17001_002",
            
            # Housing
            "median_home_value": "B25077_001",
            "home_value": "B25077_001",
            "housing_units": "B25001_001",
            "total_housing_units": "B25001_001",
            "renter_occupied": "B25003_003",
            "owner_occupied": "B25003_002",
            
            # Employment
            "unemployment_rate": "B23025_005",  # Unemployed
            "unemployment": "B23025_005",
            "labor_force": "B23025_002",
            
            # Demographics
            "median_age": "B01002_001",
            "age": "B01002_001",
            
            # Education
            "bachelors_degree": "B15003_022",  # Bachelor's degree
            "college_degree": "B15003_022",
            "high_school": "B15003_017",  # High school graduate
        }
    
    def _init_geography_patterns(self):
        """Initialize geography parsing patterns."""
        # State patterns
        self.state_abbrevs = {
            'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
            'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
            'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
            'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
            'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
            'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
            'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
            'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
            'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
            'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
            'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
            'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
            'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
        }
        
        # Reverse mapping
        self.state_names = {v.lower(): k for k, v in self.state_abbrevs.items()}
    
    def _map_variables(self, variables: List[str]) -> List[str]:
        """Map human-readable variable names to Census variable codes."""
        mapped_vars = []
        for var in variables:
            var_lower = var.lower().strip()
            
            # Direct mapping
            if var_lower in self.variable_mappings:
                mapped_vars.append(self.variable_mappings[var_lower])
            # If already a Census variable code (starts with B, C, etc.)
            elif re.match(r'^[A-Z]\d{5}_\d{3}$', var.upper()):
                mapped_vars.append(var.upper())
            else:
                # Fuzzy matching for partial matches
                best_match = self._fuzzy_match_variable(var_lower)
                if best_match:
                    mapped_vars.append(best_match)
                else:
                    logger.warning(f"Could not map variable: {var}")
                    mapped_vars.append(var)  # Pass through, let R handle the error
        
        return mapped_vars
    
    def _fuzzy_match_variable(self, var: str) -> Optional[str]:
        """Attempt fuzzy matching for variable names."""
        var = var.lower()
        
        # Check for partial matches
        for key, code in self.variable_mappings.items():
            if var in key or key in var:
                return code
        
        # Check for keyword matches
        if 'income' in var:
            return self.variable_mappings['median_income']
        elif 'poverty' in var:
            return self.variable_mappings['poverty_rate']
        elif 'population' in var or 'pop' in var:
            return self.variable_mappings['population']
        elif 'housing' in var or 'home' in var:
            return self.variable_mappings['housing_units']
        elif 'unemployment' in var or 'jobless' in var:
            return self.variable_mappings['unemployment_rate']
        
        return None
    
    def _parse_location(self, location: str) -> Dict[str, Any]:
        """
        Parse location string into geography components for R tidycensus.
        
        Examples:
        - "Maryland" → state-level
        - "Baltimore, MD" → place-level  
        - "Baltimore County, MD" → county-level
        - "United States" → national-level
        """
        location = location.strip()
        
        # National level
        if location.lower() in ['united states', 'usa', 'us', 'america']:
            return {
                'geography': 'us',
                'state': None,
                'county': None,
                'place': None
            }
        
        # Major cities - CHECK FIRST (before state name matching)
        location_lower = location.lower()
        major_cities = {
            'new york': {'state': 'NY', 'place': 'New York city'},
            'new york city': {'state': 'NY', 'place': 'New York city'},
            'nyc': {'state': 'NY', 'place': 'New York city'},
            'los angeles': {'state': 'CA', 'place': 'Los Angeles city'},
            'chicago': {'state': 'IL', 'place': 'Chicago city'},
            'houston': {'state': 'TX', 'place': 'Houston city'},
            'philadelphia': {'state': 'PA', 'place': 'Philadelphia city'},
            'phoenix': {'state': 'AZ', 'place': 'Phoenix city'},
            'san antonio': {'state': 'TX', 'place': 'San Antonio city'},
            'san diego': {'state': 'CA', 'place': 'San Diego city'},
            'dallas': {'state': 'TX', 'place': 'Dallas city'},
            'san jose': {'state': 'CA', 'place': 'San Jose city'},
            'baltimore': {'state': 'MD', 'place': 'Baltimore city'},
        }
        
        if location_lower in major_cities:
            city_info = major_cities[location_lower]
            return {
                'geography': 'place',
                'state': city_info['state'],
                'county': None,
                'place': city_info['place']
            }
        
        # Parse state patterns with comma
        if ',' in location:
            # Format: "City, ST" or "County, ST"
            parts = [p.strip() for p in location.split(',')]
            if len(parts) == 2:
                place_name, state_part = parts
                state_code = self._normalize_state(state_part)
                
                if state_code:
                    # Determine if county or place
                    if 'county' in place_name.lower():
                        # County level
                        county_name = place_name.replace(' County', '').replace(' county', '')
                        return {
                            'geography': 'county',
                            'state': state_code,
                            'county': county_name,
                            'place': None
                        }
                    else:
                        # Place level (city/town)
                        # Add 'city' suffix for major cities if not present
                        if not any(suffix in place_name.lower() for suffix in ['city', 'town', 'village']):
                            place_name = f"{place_name} city"
                        
                        return {
                            'geography': 'place',
                            'state': state_code,
                            'county': None,
                            'place': place_name
                        }
        
        # Single location - check if it's a state LAST (after major cities)
        state_code = self._normalize_state(location)
        if state_code:
            return {
                'geography': 'state',
                'state': state_code,
                'county': None,
                'place': None
            }
        
        # Default to place search within US - add 'city' suffix for common cities
        if not any(suffix in location.lower() for suffix in ['city', 'town', 'village', 'county']):
            location = f"{location} city"
        
        return {
            'geography': 'place',
            'state': None,  # Search all states
            'county': None,
            'place': location
        }
    
    def _normalize_state(self, state_input: str) -> Optional[str]:
        """Normalize state name/abbreviation to standard abbreviation."""
        state_input = state_input.strip()
        
        # Check if already an abbreviation
        if state_input.upper() in self.state_abbrevs:
            return state_input.upper()
        
        # Check if full state name
        if state_input.lower() in self.state_names:
            return self.state_names[state_input.lower()]
        
        return None
    
    async def get_acs_data(self, location: str, variables: List[str],
                          year: int = 2023, survey: str = "acs5",
                          context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get ACS data for specified location and variables.
        
        Args:
            location: Human-readable location name
            variables: List of variable names (human-readable or codes)
            year: ACS year
            survey: ACS survey type (acs1 or acs5)
            context: Optional context from knowledge base
            
        Returns:
            Dictionary with Census data and metadata
        """
        try:
            # Map variables to Census codes
            census_variables = self._map_variables(variables)
            
            # Parse location
            location_data = self._parse_location(location)
            
            logger.info(f"Retrieving ACS data: {location} ({location_data['geography']}) "
                       f"for variables {census_variables}")
            
            # Prepare R script arguments
            location_json = json.dumps(location_data)
            variables_json = json.dumps(census_variables)
            
            # Execute R script
            result = await self._execute_r_script(
                location_json, variables_json, year, survey
            )
            
            # Process and format result
            formatted_result = self._format_census_data(
                result, variables, census_variables, location, year, survey
            )
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error retrieving ACS data: {str(e)}")
            return {
                'error': str(e),
                'location': location,
                'variables': variables,
                'success': False
            }
    
    async def _execute_r_script(self, location_json: str, variables_json: str,
                               year: int, survey: str) -> Dict[str, Any]:
        """Execute R script subprocess to get Census data."""
        try:
            # Prepare command
            cmd = [
                self.config.r_executable,
                str(self.r_script_path),
                location_json,
                variables_json,
                str(year),
                survey
            ]
            
            # Set environment variables
            env = os.environ.copy()
            if self.config.census_api_key:
                env['CENSUS_API_KEY'] = self.config.census_api_key
            
            # Execute subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.r_timeout
            )
            
            # Check for errors
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown R error"
                raise RuntimeError(f"R script failed: {error_msg}")
            
            # Parse JSON output
            output = stdout.decode('utf-8')
            result = json.loads(output)
            
            return result
            
        except asyncio.TimeoutError:
            raise RuntimeError(f"R script timeout after {self.config.r_timeout} seconds")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse R script output: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"R script execution failed: {str(e)}")
    
    def _format_census_data(self, r_result: Dict, original_variables: List[str],
                           census_variables: List[str], location: str,
                           year: int, survey: str) -> Dict[str, Any]:
        """Format Census data result for MCP response."""
        if not r_result.get('success', False):
            return {
                'error': r_result.get('error', 'Unknown error from R script'),
                'location': location,
                'variables': original_variables,
                'success': False
            }
        
        try:
            # Extract data from R result
            census_data = r_result.get('data', [])
            
            # Format data by variable
            formatted_data = {}
            
            # Create mapping from original to census variables
            var_mapping = dict(zip(original_variables, census_variables))
            
            for i, original_var in enumerate(original_variables):
                census_var = census_variables[i] if i < len(census_variables) else None
                
                # Find data for this variable
                var_data = None
                for row in census_data:
                    if row.get('variable') == census_var:
                        var_data = {
                            'estimate': row.get('estimate'),
                            'moe': row.get('moe'),
                            'variable_code': census_var,
                            'name': row.get('NAME', location)
                        }
                        break
                
                if var_data:
                    formatted_data[original_var] = var_data
                else:
                    formatted_data[original_var] = {
                        'error': f"No data found for variable {census_var}",
                        'variable_code': census_var
                    }
            
            # Add metadata
            result = {
                'data': formatted_data,
                'location': location,
                'variables': original_variables,
                'source': r_result.get('source', 'US Census Bureau American Community Survey'),
                'year': year,
                'survey': survey.upper(),
                'geography': r_result.get('geography', 'unknown'),
                'success': True
            }
            
            # Flatten for easier access in response formatting
            for var, data in formatted_data.items():
                if 'error' not in data:
                    result[var] = data
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting Census data: {str(e)}")
            return {
                'error': f"Error formatting data: {str(e)}",
                'location': location,
                'variables': original_variables,
                'success': False
            }

    def add_variable_mapping(self, key: str, census_code: str):
        """Add new variable mapping (for dynamic expansion)."""
        self.variable_mappings[key.lower()] = census_code
        logger.info(f"Added variable mapping: {key} → {census_code}")
    
    def get_available_variables(self) -> Dict[str, str]:
        """Get all available variable mappings."""
        return self.variable_mappings.copy()

