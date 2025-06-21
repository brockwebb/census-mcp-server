"""
R Data Retrieval Engine for Census MCP Server - Complete AI-Optimized Version

Uses pre-built semantic index for fast variable mapping with robust fallbacks.
Container-ready with core mappings for reliability.
"""

import asyncio
import json
import logging
import subprocess
import sqlite3
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import os

from utils.config import get_config

logger = logging.getLogger(__name__)

class RDataRetrieval:
    """
    AI-optimized R subprocess interface for Census data retrieval.
    
    Hybrid approach:
    - Core static mappings for reliability (50 essential variables)
    - Semantic index lookup for comprehensiveness (10k+ variables)  
    - Dynamic tidycensus fallback for edge cases
    - <50ms target for common queries
    """
    
    def __init__(self, r_script_path: Optional[Path] = None):
        """Initialize AI-optimized R data retrieval engine."""
        self.config = get_config()
        self.r_script_path = r_script_path or self.config.r_script_path
        
        # Core static mappings - ALWAYS available
        self._init_core_mappings()
        
        # Load AI-optimized semantic index
        self.semantic_index = self._load_semantic_index()
        self.search_db_path = self.config.config_dir / "search_index.db"
        
        # Ensure R script exists
        self._ensure_r_script()
        
        # Initialize geography patterns
        self._init_geography_patterns()
        
        logger.info(f"AI-optimized R engine initialized:")
        logger.info(f"  Core mappings: {len(self.core_mappings)} variables")
        logger.info(f"  Semantic index: {len(self.semantic_index)} variables")
    
    def _init_core_mappings(self):
        """Initialize core variable mappings - the absolutely critical ones."""
        # These ~100 variables handle 80-90% of queries
        self.core_mappings = {
            # Population
            'population': 'B01003_001',
            'total_population': 'B01003_001',
            'pop': 'B01003_001',
            'people': 'B01003_001',
            
            # Sex/Gender
            'male': 'B01001_002',
            'female': 'B01001_026',
            'sex': 'B01001_001',  # Total for sex breakdown
            'gender': 'B01001_001',
            'men': 'B01001_002',
            'women': 'B01001_026',
            
            # Age Demographics
            'median_age': 'B01002_001',
            'age': 'B01002_001',
            'under_18': 'B09001_001',  # Children
            'children': 'B09001_001',
            'kids': 'B09001_001',
            'over_65': 'B01001_020',  # Seniors (approximate)
            'seniors': 'B01001_020',
            'elderly': 'B01001_020',
            'working_age': 'B23025_001',  # 16+ labor force universe
            
            # Race/Ethnicity
            'white_alone': 'B02001_002',
            'black_alone': 'B02001_003',
            'african_american': 'B02001_003',
            'asian_alone': 'B02001_005',
            'hispanic': 'B03003_003',
            'latino': 'B03003_003',
            'native_american': 'B02001_004',
            'american_indian': 'B02001_004',
            'pacific_islander': 'B02001_006',
            'two_or_more_races': 'B02001_008',
            'multiracial': 'B02001_008',
            'mixed_race': 'B02001_008',
            
            # Income
            'median_income': 'B19013_001',
            'median_household_income': 'B19013_001',
            'household_income': 'B19013_001',
            'income': 'B19013_001',
            'per_capita_income': 'B19301_001',
            'median_family_income': 'B19113_001',
            'family_income': 'B19113_001',
            'mean_household_income': 'B19025_001',
            'average_income': 'B19025_001',
            
            # Poverty
            'poverty_rate': 'B17001_002',
            'poverty': 'B17001_002',
            'below_poverty': 'B17001_002',
            'poor': 'B17001_002',
            'poverty_level': 'B17001_001',  # Universe for poverty calculations
            'child_poverty': 'B17001_004',  # Under 18 in poverty
            'senior_poverty': 'B17001_015',  # 65+ in poverty
            
            # Employment
            'unemployment_rate': 'B23025_005',
            'unemployment': 'B23025_005',
            'unemployed': 'B23025_005',
            'labor_force': 'B23025_002',
            'employment': 'B23025_002',
            'employed': 'B23025_004',
            'not_in_labor_force': 'B23025_007',
            'labor_force_participation': 'B23025_001',
            
            # Education
            'bachelors_degree': 'B15003_022',
            'college_degree': 'B15003_022',
            'bachelor': 'B15003_022',
            'high_school': 'B15003_017',
            'high_school_graduate': 'B15003_017',
            'graduate_degree': 'B15003_023',  # Masters
            'masters_degree': 'B15003_023',
            'doctorate': 'B15003_025',
            'phd': 'B15003_025',
            'less_than_high_school': 'B15003_001',  # Need to calculate
            'some_college': 'B15003_019',
            'associates_degree': 'B15003_021',
            
            # Housing
            'median_home_value': 'B25077_001',
            'home_value': 'B25077_001',
            'house_value': 'B25077_001',
            'property_value': 'B25077_001',
            'housing_units': 'B25001_001',
            'total_housing_units': 'B25001_001',
            'occupied_housing': 'B25002_002',
            'vacant_housing': 'B25002_003',
            'renter_occupied': 'B25003_003',
            'owner_occupied': 'B25003_002',
            'median_rent': 'B25064_001',
            'rent': 'B25064_001',
            'gross_rent': 'B25064_001',
            'homeownership_rate': 'B25003_001',  # Universe for ownership calculation
            
            # Marital Status
            'married': 'B12001_004',  # Never married male + female
            'single': 'B12001_003',
            'never_married': 'B12001_003',
            'divorced': 'B12001_010',
            'widowed': 'B12001_009',
            'separated': 'B12001_008',
            
            # Veteran Status
            'veterans': 'B21001_002',
            'veteran': 'B21001_002',
            'military': 'B21001_002',
            'non_veteran': 'B21001_003',
            
            # Disability Status
            'disabled': 'B18101_001',  # With a disability
            'disability': 'B18101_001',
            'no_disability': 'B18101_001',  # Need calculated field
            
            # Foreign Born/Citizenship
            'foreign_born': 'B05002_013',
            'native_born': 'B05002_002',
            'immigrants': 'B05002_013',
            'citizens': 'B05001_002',
            'non_citizens': 'B05001_006',
            'naturalized': 'B05002_014',
            
            # Language
            'english_only': 'B16001_002',
            'spanish': 'B16001_003',
            'other_language': 'B16001_001',  # Universe
            'speaks_english_well': 'B16004_003',
            'limited_english': 'B16004_005',
            
            # Transportation/Commuting
            'commute_time': 'B08303_001',
            'travel_time': 'B08303_001',
            'drives_alone': 'B08301_010',
            'carpool': 'B08301_011',
            'public_transportation': 'B08301_010',
            'walks': 'B08301_019',
            'works_from_home': 'B08301_021',
            
            # Family Structure
            'households': 'B25044_001',
            'families': 'B11001_001',
            'family_households': 'B11001_002',
            'non_family_households': 'B11001_007',
            'married_couple_families': 'B11001_003',
            'single_parent': 'B11001_006',  # Female householder
            'single_mother': 'B11001_006',
            'single_father': 'B11001_005',  # Male householder
            
            # Industry (Top sectors)
            'agriculture': 'C24030_003',
            'construction': 'C24030_007',
            'manufacturing': 'C24030_008',
            'retail': 'C24030_015',
            'healthcare': 'C24030_024',
            'education': 'C24030_023',
            'government': 'C24030_027',
            
            # Occupation (Major groups)
            'management': 'C24010_003',
            'professional': 'C24010_005',
            'service': 'C24010_019',
            'sales': 'C24010_023',
            'office': 'C24010_025',
            'construction_occupation': 'C24010_031',
            'production': 'C24010_037',
            
            # Common natural language variations
            'how_much_do_people_make': 'B19013_001',
            'salary': 'B19013_001',
            'wages': 'B19013_001',
            'earnings': 'B19013_001',
            'cost_of_housing': 'B25077_001',
            'house_prices': 'B25077_001',
            'home_prices': 'B25077_001',
            'how_many_people': 'B01003_001',
            'demographics': 'B01003_001',
            'stats': 'B01003_001',
            'data': 'B01003_001',
        }
    
    def _load_semantic_index(self) -> Dict[str, Dict]:
        """Load the AI-built semantic index with fallback handling."""
        semantic_path = self.config.config_dir / "semantic_index.json"
        
        if not semantic_path.exists():
            logger.warning("⚠️ Semantic index not found - using core mappings + dynamic search")
            return {}
        
        try:
            with open(semantic_path, 'r') as f:
                index_data = json.load(f)
            
            variables = index_data.get('variables', {})
            logger.info(f"✅ Loaded semantic index: {len(variables)} variables")
            return variables
            
        except Exception as e:
            logger.error(f"❌ Failed to load semantic index: {e}")
            logger.warning("⚠️ Falling back to core mappings + dynamic search")
            return {}
    
    def _map_variables(self, variables: List[str]) -> List[str]:
        """
        AI-optimized hybrid variable mapping with robust fallbacks.
        
        1. Try core mappings (instant, always available)
        2. Try semantic index (fast, comprehensive)
        3. Try SQLite full-text search (medium speed)
        4. Check if already Census variable code
        5. Fall back to original variable (R will handle error)
        """
        mapped_vars = []
        
        for var in variables:
            var_lower = var.lower().strip()
            
            # Step 1: Core mappings (always works, instant)
            if var_lower in self.core_mappings:
                mapped_var = self.core_mappings[var_lower]
                logger.debug(f"✅ Core mapping: {var} → {mapped_var}")
                mapped_vars.append(mapped_var)
                continue
            
            # Step 2: Semantic index lookup
            mapped_var = self._semantic_index_lookup(var_lower)
            if mapped_var:
                mapped_vars.append(mapped_var)
                continue
            
            # Step 3: SQLite full-text search
            mapped_var = self._sqlite_search(var_lower)
            if mapped_var:
                mapped_vars.append(mapped_var)
                continue
            
            # Step 4: Check if already a Census variable code
            if re.match(r'^[A-Z]\d{5}_\d{3}[A-Z]?$', var.upper()):
                mapped_vars.append(var.upper())
                logger.debug(f"✅ Direct Census code: {var}")
                continue
            
            # Step 5: Fuzzy matching fallback
            fuzzy_match = self._fuzzy_match_variable(var_lower)
            if fuzzy_match:
                mapped_vars.append(fuzzy_match)
                continue
            
            # Step 6: Pass through original (R will handle error gracefully)
            logger.warning(f"⚠️ No mapping found for: {var} - passing to R")
            mapped_vars.append(var)
        
        return mapped_vars
    
    def _semantic_index_lookup(self, query: str) -> Optional[str]:
        """Fast lookup in semantic index using aliases and keywords."""
        if not self.semantic_index:
            return None
        
        for var_id, var_data in self.semantic_index.items():
            # Check direct aliases
            aliases = var_data.get('aliases', [])
            if query in [alias.lower() for alias in aliases]:
                logger.debug(f"✅ Semantic alias match: {query} → {var_id}")
                return var_id
            
            # Check semantic keywords
            keywords = var_data.get('semantic_keywords', [])
            if query in [kw.lower() for kw in keywords]:
                logger.debug(f"✅ Semantic keyword match: {query} → {var_id}")
                return var_id
        
        return None
    
    def _sqlite_search(self, query: str) -> Optional[str]:
        """SQLite full-text search for flexible matching."""
        if not self.search_db_path.exists():
            return None
        
        try:
            conn = sqlite3.connect(self.search_db_path)
            cursor = conn.cursor()
            
            # FTS query with relevance ranking
            cursor.execute('''
                SELECT variable_id, rank FROM (
                    SELECT variable_id, 
                           bm25(variables_fts) as rank
                    FROM variables_fts 
                    WHERE variables_fts MATCH ?
                    ORDER BY rank
                    LIMIT 1
                )
            ''', (query,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                var_id, rank = result
                logger.debug(f"✅ SQLite FTS match: {query} → {var_id} (rank: {rank:.2f})")
                return var_id
            
        except Exception as e:
            logger.warning(f"SQLite search failed for '{query}': {e}")
        
        return None
    
    def _fuzzy_match_variable(self, var: str) -> Optional[str]:
        """Attempt fuzzy matching for variable names."""
        var = var.lower().strip()
        
        # Check for partial matches in core mappings
        for key, code in self.core_mappings.items():
            if var in key or key in var:
                logger.debug(f"✅ Fuzzy core match: {var} → {code} (via {key})")
                return code
        
        # Check for keyword matches
        keyword_mappings = {
            'income': 'B19013_001',
            'salary': 'B19013_001',
            'earn': 'B19013_001',
            'make': 'B19013_001',
            'poverty': 'B17001_002',
            'poor': 'B17001_002',
            'population': 'B01003_001',
            'people': 'B01003_001',
            'housing': 'B25001_001',
            'home': 'B25077_001',
            'house': 'B25077_001',
            'unemployment': 'B23025_005',
            'jobless': 'B23025_005',
            'unemployed': 'B23025_005',
            'rent': 'B25064_001',
            'age': 'B01002_001',
            'education': 'B15003_022',
            'college': 'B15003_022',
            'school': 'B15003_017',
        }
        
        for keyword, code in keyword_mappings.items():
            if keyword in var:
                logger.debug(f"✅ Fuzzy keyword match: {var} → {code} (via {keyword})")
                return code
        
        return None
    
    def _ensure_r_script(self):
        """Ensure R script exists, create if needed."""
        if not self.r_script_path.exists():
            logger.info("Creating R script for Census data retrieval")
            success = self.config.save_r_script()
            if not success:
                raise RuntimeError("Failed to create R script")
    
    def _init_geography_patterns(self):
        """Initialize geography parsing patterns."""
        # State patterns including territories
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
            'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
            'PR': 'Puerto Rico'
        }
        
        # Reverse mapping
        self.state_names = {v.lower(): k for k, v in self.state_abbrevs.items()}
    
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
            return {'geography': 'us', 'state': None, 'county': None, 'place': None}
        
        # Major cities - prioritize these for accuracy
        location_lower = location.lower()
        major_cities = {
            'new york': {'state': 'NY', 'place': 'New York city'},
            'new york city': {'state': 'NY', 'place': 'New York city'},
            'nyc': {'state': 'NY', 'place': 'New York city'},
            'los angeles': {'state': 'CA', 'place': 'Los Angeles city'},
            'la': {'state': 'CA', 'place': 'Los Angeles city'},
            'chicago': {'state': 'IL', 'place': 'Chicago city'},
            'houston': {'state': 'TX', 'place': 'Houston city'},
            'philadelphia': {'state': 'PA', 'place': 'Philadelphia city'},
            'phoenix': {'state': 'AZ', 'place': 'Phoenix city'},
            'san antonio': {'state': 'TX', 'place': 'San Antonio city'},
            'san diego': {'state': 'CA', 'place': 'San Diego city'},
            'dallas': {'state': 'TX', 'place': 'Dallas city'},
            'san jose': {'state': 'CA', 'place': 'San Jose city'},
            'baltimore': {'state': 'MD', 'place': 'Baltimore city'},
            'boston': {'state': 'MA', 'place': 'Boston city'},
            'washington': {'state': 'DC', 'place': 'Washington city'},
            'dc': {'state': 'DC', 'place': 'Washington city'},
        }
        
        if location_lower in major_cities:
            city_info = major_cities[location_lower]
            return {
                'geography': 'place',
                'state': city_info['state'],
                'county': None,
                'place': city_info['place']
            }
        
        # Parse comma-separated patterns: "City, ST" or "County, ST"
        if ',' in location:
            parts = [p.strip() for p in location.split(',')]
            if len(parts) == 2:
                place_name, state_part = parts
                state_code = self._normalize_state(state_part)
                
                if state_code:
                    # County level
                    if 'county' in place_name.lower():
                        county_name = place_name.replace(' County', '').replace(' county', '')
                        return {
                            'geography': 'county',
                            'state': state_code,
                            'county': county_name,
                            'place': None
                        }
                    else:
                        # Place level (city/town)
                        # Ensure proper formatting for tidycensus
                        if not any(suffix in place_name.lower() for suffix in ['city', 'town', 'village']):
                            place_name = f"{place_name} city"
                        
                        return {
                            'geography': 'place',
                            'state': state_code,
                            'county': None,
                            'place': place_name
                        }
        
        # Single location - check if it's a state
        state_code = self._normalize_state(location)
        if state_code:
            return {
                'geography': 'state',
                'state': state_code,
                'county': None,
                'place': None
            }
        
        # Default to place search (assume it's a city)
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
    
    async def get_acs_data(self, location: str, variables: List[str], year: int = 2023,
                          survey: str = "acs5", context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get ACS data using AI-optimized hybrid approach.
        
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
            # AI-optimized variable mapping
            census_variables = self._map_variables(variables)
            
            # Parse location
            location_data = self._parse_location(location)
            
            logger.info(f"AI-optimized retrieval: {location} ({location_data['geography']}) "
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
        """Add new variable mapping to core mappings (for dynamic expansion)."""
        self.core_mappings[key.lower()] = census_code
        logger.info(f"Added core variable mapping: {key} → {census_code}")
    
    def get_available_variables(self) -> Dict[str, str]:
        """Get all available variable mappings."""
        all_variables = self.core_mappings.copy()
        
        # Add semantic index variables if available
        if self.semantic_index:
            for var_id, var_data in self.semantic_index.items():
                label = var_data.get('label', var_id)
                all_variables[label.lower()] = var_id
        
        return all_variables
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics for monitoring."""
        return {
            'core_mappings_count': len(self.core_mappings),
            'semantic_index_count': len(self.semantic_index),
            'semantic_index_available': bool(self.semantic_index),
            'sqlite_db_available': self.search_db_path.exists(),
            'r_script_path': str(self.r_script_path),
            'r_executable': self.config.r_executable
        }
