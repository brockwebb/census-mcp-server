#!/usr/bin/env python3
"""
AI-Optimized Census Semantic Pipeline Builder

Fetches ALL Census variables from API, filters to useful subset, and builds
AI-optimized search structures for 300ms performance targets.

This is the "annual refresh" system that creates the semantic index that
tidycensus should have been if built for the AI era.

Usage:
    cd census-mcp-server/
    python scripts/build_semantic_index.py [--test-mode]

Requirements:
    pip install requests sqlite3 nltk

Output:
    config/semantic_index.json - Complete variable catalog with semantic enrichment
    config/search_index.db - SQLite full-text search database
    config/variable_metadata.json - Build statistics and metadata
"""

import json
import logging
import sqlite3
import requests
import re
import nltk
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from collections import defaultdict
import argparse

# Download required NLTK data (for semantic processing)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class CensusSemanticPipeline:
    """
    AI-optimized Census semantic pipeline builder.
    
    Fetches complete Census variable catalog, applies AI-optimized filtering
    and semantic enrichment, then builds fast search structures.
    """
    
    def __init__(self, test_mode: bool = False):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        self.test_mode = test_mode
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize NLTK components
        self.stop_words = set(stopwords.words('english'))
        
        # Census API endpoints
        self.census_api_base = "https://api.census.gov/data"
        self.current_year = 2022  # Most recent complete ACS data
        
        logger.info(f"🤖 Building AI-optimized Census semantic pipeline")
        logger.info(f"📁 Output directory: {self.config_dir}")
        logger.info(f"🧪 Test mode: {self.test_mode}")
    
    async def build_complete_pipeline(self):
        """Build the complete AI-optimized semantic pipeline."""
        
        logger.info("🚀 Starting AI-optimized Census pipeline build...")
        
        # Step 1: Fetch ALL Census variables
        logger.info("📡 Step 1: Fetching complete Census variable catalog...")
        all_variables = await self._fetch_all_census_variables()
        logger.info(f"   Retrieved {len(all_variables)} total variables")
        
        # Step 2: Filter to useful subset using AI criteria
        logger.info("🎯 Step 2: Filtering to AI-relevant variable subset...")
        useful_variables = self._filter_to_useful_variables(all_variables)
        logger.info(f"   Filtered to {len(useful_variables)} useful variables")
        
        # Step 3: Build semantic enrichment
        logger.info("🧠 Step 3: Building semantic enrichment...")
        enriched_variables = self._build_semantic_enrichment(useful_variables)
        logger.info(f"   Added semantic metadata to {len(enriched_variables)} variables")
        
        # Step 4: Create search structures
        logger.info("🔍 Step 4: Building AI-optimized search structures...")
        search_index = self._build_search_index(enriched_variables)
        
        # Step 5: Save all outputs
        logger.info("💾 Step 5: Saving AI-optimized pipeline outputs...")
        self._save_semantic_index(enriched_variables)
        self._save_search_database(search_index, enriched_variables)
        self._save_build_metadata(all_variables, useful_variables, enriched_variables)
        
        logger.info("✅ AI-optimized Census semantic pipeline build complete!")
        self._print_pipeline_summary(all_variables, useful_variables, enriched_variables)
    
    async def _fetch_all_census_variables(self) -> Dict[str, Dict]:
        """Fetch complete Census variable catalog from API."""
        
        variables_url = f"{self.census_api_base}/{self.current_year}/acs/acs5/variables.json"
        
        try:
            logger.info(f"   Calling Census API: {variables_url}")
            response = requests.get(variables_url, timeout=30)
            response.raise_for_status()
            
            variables_data = response.json()
            
            # Extract variables dictionary
            if 'variables' in variables_data:
                all_vars = variables_data['variables']
            else:
                all_vars = variables_data
            
            # Filter out metadata entries
            census_variables = {}
            for var_id, var_data in all_vars.items():
                if self._is_data_variable(var_id, var_data):
                    census_variables[var_id] = var_data
            
            logger.info(f"   ✅ Successfully fetched {len(census_variables)} Census variables")
            
            if self.test_mode:
                # In test mode, use only first 100 variables
                test_vars = dict(list(census_variables.items())[:100])
                logger.info(f"   🧪 Test mode: Using {len(test_vars)} variables")
                return test_vars
                
            return census_variables
            
        except requests.RequestException as e:
            logger.error(f"   ❌ Failed to fetch Census variables: {e}")
            raise
        except Exception as e:
            logger.error(f"   ❌ Error processing Census variables: {e}")
            raise
    
    def _is_data_variable(self, var_id: str, var_data: Dict) -> bool:
        """Check if this is an actual data variable (not metadata)."""
        
        # Skip non-variable entries
        if not isinstance(var_data, dict):
            return False
        
        # Must have a label
        if 'label' not in var_data:
            return False
        
        # Skip geographic variables and annotations
        if var_id in ['for', 'in', 'ucgid', 'NAME']:
            return False
        
        # Must match Census variable pattern (like B01003_001)
        if not re.match(r'^[A-Z]\d{5}_\d{3}[A-Z]?$', var_id):
            return False
        
        return True
    
    def _filter_to_useful_variables(self, all_variables: Dict) -> Dict[str, Dict]:
        """Filter to variables people actually ask about using AI criteria."""
        
        useful_variables = {}
        
        # Priority categories (high-value for AI queries)
        priority_patterns = [
            # Demographics & Population
            r'total.*population|population.*total',
            r'median age|age.*median',
            
            # Income & Economic
            r'median.*income|income.*median',
            r'poverty|below.*poverty',
            r'unemployment|unemployed',
            
            # Housing
            r'median.*value|value.*median|home.*value',
            r'median.*rent|rent.*median',
            r'housing.*units|units.*housing',
            
            # Education
            r'bachelor|college|university|degree|education',
            r'high school|diploma',
            
            # Race & Ethnicity
            r'white alone|black.*african american|asian alone|american indian|hispanic.*latino',
            
            # Occupations (earnings/employment by occupation)
            r'occupation.*earnings|earnings.*occupation',
            r'management.*earnings|education.*earnings|healthcare.*earnings',
            
            # Key tables (known high-value tables)
            r'^B01003|^B19013|^B25077|^B25064|^B17001|^B23025|^B15003|^B24080'
        ]
        
        # Exclude patterns (low-value for AI queries)
        exclude_patterns = [
            r'annotation|flag|status',
            r'margin of error',
            r'universe',
        ]
        
        for var_id, var_data in all_variables.items():
            label = var_data.get('label', '').lower()
            concept = var_data.get('concept', '').lower()
            combined_text = f"{label} {concept}"
            
            # Check exclusion patterns first
            if any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in exclude_patterns):
                continue
            
            # Check priority patterns
            if any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in priority_patterns):
                useful_variables[var_id] = var_data
                continue
            
            # Include variables from high-value table prefixes
            table_prefix = var_id[:6]  # e.g., B01003 from B01003_001
            if table_prefix in self._get_priority_tables():
                useful_variables[var_id] = var_data
        
        return useful_variables
    
    def _get_priority_tables(self) -> Set[str]:
        """Get Census table prefixes known to be high-value for AI queries."""
        return {
            'B01003',  # Total Population
            'B19013',  # Median Household Income
            'B25077',  # Median Home Value
            'B25064',  # Median Gross Rent
            'B17001',  # Poverty Status
            'B23025',  # Employment Status
            'B15003',  # Educational Attainment
            'B24080',  # Occupation by Earnings
            'B02001',  # Race
            'B03003',  # Hispanic or Latino Origin
            'B01002',  # Median Age
            'B25001',  # Housing Units
            'B25003',  # Tenure (Owner/Renter)
        }
    
    def _build_semantic_enrichment(self, useful_variables: Dict) -> Dict[str, Dict]:
        """Add semantic metadata for AI-optimized search."""
        
        enriched_variables = {}
        
        for var_id, var_data in useful_variables.items():
            
            # Extract semantic keywords from label and concept
            semantic_keywords = self._extract_semantic_keywords(var_data)
            
            # Determine statistical measure type
            measure_type = self._determine_measure_type(var_data)
            
            # Generate natural language aliases
            aliases = self._generate_aliases(var_data, semantic_keywords)
            
            # Create enriched entry
            enriched_variables[var_id] = {
                **var_data,  # Original Census metadata
                'semantic_keywords': semantic_keywords,
                'measure_type': measure_type,
                'aliases': aliases,
                'search_text': self._build_search_text(var_data, semantic_keywords, aliases),
                'ai_relevance_score': self._calculate_relevance_score(var_data, semantic_keywords)
            }
        
        return enriched_variables
    
    def _extract_semantic_keywords(self, var_data: Dict) -> List[str]:
        """Extract semantic keywords from Census variable metadata."""
        
        label = var_data.get('label', '')
        concept = var_data.get('concept', '')
        
        # Combine and clean text
        combined_text = f"{label} {concept}".lower()
        
        # Tokenize and filter
        tokens = word_tokenize(combined_text)
        
        # Remove stop words, punctuation, and short words
        keywords = []
        for token in tokens:
            if (token.isalpha() and
                len(token) > 2 and
                token not in self.stop_words and
                token not in ['estimate', 'total', 'universe']):
                keywords.append(token)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(keywords))
    
    def _determine_measure_type(self, var_data: Dict) -> str:
        """Determine the type of statistical measure."""
        
        label = var_data.get('label', '').lower()
        
        if 'median' in label:
            return 'median'
        elif 'mean' in label or 'average' in label:
            return 'mean'
        elif 'total' in label or 'count' in label:
            return 'total'
        elif 'percentage' in label or 'percent' in label:
            return 'percentage'
        elif 'rate' in label:
            return 'rate'
        else:
            return 'count'  # Default assumption
    
    def _generate_aliases(self, var_data: Dict, keywords: List[str]) -> List[str]:
        """Generate natural language aliases for AI queries."""
        
        aliases = []
        label = var_data.get('label', '').lower()
        
        # Common alias patterns
        alias_mappings = {
            'income': ['salary', 'earnings', 'wages', 'pay', 'money'],
            'population': ['people', 'residents', 'inhabitants'],
            'housing': ['home', 'house', 'property'],
            'value': ['cost', 'price', 'worth'],
            'unemployment': ['jobless', 'unemployed'],
            'education': ['school', 'college', 'university'],
            'bachelor': ['college degree', 'university degree'],
            'rent': ['rental'],
            'occupation': ['job', 'work', 'career'],
            'earnings': ['income', 'salary', 'pay'],
        }
        
        # Add aliases based on keywords
        for keyword in keywords:
            if keyword in alias_mappings:
                aliases.extend(alias_mappings[keyword])
        
        # Add common question patterns
        if 'income' in keywords or 'earnings' in keywords:
            aliases.extend(['make', 'earn', 'get paid'])
        
        if 'population' in keywords:
            aliases.extend(['how many people', 'live'])
        
        if 'value' in keywords and 'home' in label:
            aliases.extend(['expensive', 'cost of housing'])
        
        # Remove duplicates
        return list(set(aliases))
    
    def _build_search_text(self, var_data: Dict, keywords: List[str], aliases: List[str]) -> str:
        """Build searchable text for full-text search."""
        
        components = [
            var_data.get('label', ''),
            var_data.get('concept', ''),
            ' '.join(keywords),
            ' '.join(aliases)
        ]
        
        return ' '.join(components).lower()
    
    def _calculate_relevance_score(self, var_data: Dict, keywords: List[str]) -> float:
        """Calculate AI relevance score for prioritization."""
        
        score = 0.0
        label = var_data.get('label', '').lower()
        
        # High-value keywords boost score
        high_value_terms = ['median', 'total', 'population', 'income', 'housing', 'education']
        for term in high_value_terms:
            if term in keywords:
                score += 1.0
        
        # Median measures are preferred over means
        if 'median' in label:
            score += 2.0
        elif 'mean' in label:
            score += 0.5
        
        # Occupation earnings are valuable
        if 'occupation' in keywords and 'earnings' in keywords:
            score += 1.5
        
        # Demographic breakdowns are important
        race_ethnicity_terms = ['white', 'black', 'asian', 'hispanic', 'latino']
        if any(term in keywords for term in race_ethnicity_terms):
            score += 1.0
        
        return score
    
    def _build_search_index(self, enriched_variables: Dict) -> Dict:
        """Build optimized search index structures."""
        
        # Create concept groups for faster lookup
        concept_groups = defaultdict(list)
        keyword_index = defaultdict(list)
        alias_index = defaultdict(list)
        
        for var_id, var_data in enriched_variables.items():
            
            # Group by concept
            concept = var_data.get('concept', 'Other')
            concept_groups[concept].append(var_id)
            
            # Index by keywords
            for keyword in var_data.get('semantic_keywords', []):
                keyword_index[keyword].append(var_id)
            
            # Index by aliases
            for alias in var_data.get('aliases', []):
                alias_index[alias].append(var_id)
        
        return {
            'concept_groups': dict(concept_groups),
            'keyword_index': dict(keyword_index),
            'alias_index': dict(alias_index),
            'build_timestamp': datetime.now().isoformat()
        }
    
    def _save_semantic_index(self, enriched_variables: Dict):
        """Save the complete semantic index."""
        
        output_data = {
            'version': '2.0',
            'build_date': datetime.now().isoformat(),
            'description': 'AI-optimized Census semantic index built from complete variable catalog',
            'total_variables': len(enriched_variables),
            'data_source': f'Census API {self.current_year} ACS 5-Year',
            'variables': enriched_variables
        }
        
        output_path = self.config_dir / "semantic_index.json"
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"   💾 Saved semantic index: {output_path}")
    
    def _save_search_database(self, search_index: Dict, enriched_variables: Dict):
        """Save SQLite full-text search database."""
        
        db_path = self.config_dir / "search_index.db"
        
        # Remove existing database
        if db_path.exists():
            db_path.unlink()
        
        # Create new database with FTS
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create FTS table
        cursor.execute('''
            CREATE VIRTUAL TABLE variables_fts USING fts5(
                variable_id,
                label,
                concept,
                search_text,
                keywords,
                aliases,
                measure_type,
                relevance_score
            )
        ''')
        
        # Insert all variables
        for var_id, var_data in enriched_variables.items():
            cursor.execute('''
                INSERT INTO variables_fts VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                var_id,
                var_data.get('label', ''),
                var_data.get('concept', ''),
                var_data.get('search_text', ''),
                ' '.join(var_data.get('semantic_keywords', [])),
                ' '.join(var_data.get('aliases', [])),
                var_data.get('measure_type', ''),
                var_data.get('ai_relevance_score', 0.0)
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"   💾 Saved search database: {db_path}")
    
    def _save_build_metadata(self, all_variables: Dict, useful_variables: Dict, enriched_variables: Dict):
        """Save build metadata and statistics."""
        
        metadata = {
            'build_info': {
                'version': '2.0',
                'build_date': datetime.now().isoformat(),
                'builder': 'AI-Optimized Census Semantic Pipeline',
                'test_mode': self.test_mode,
                'census_year': self.current_year
            },
            'statistics': {
                'total_census_variables': len(all_variables),
                'filtered_useful_variables': len(useful_variables),
                'final_enriched_variables': len(enriched_variables),
                'filter_ratio': f"{len(useful_variables)/len(all_variables)*100:.1f}%",
                'top_concepts': self._get_top_concepts(enriched_variables)
            },
            'performance_targets': {
                'lookup_time': '<50ms (local JSON/SQLite)',
                'coverage_estimate': f'{len(enriched_variables)} variables covering most AI queries',
                'fallback': 'Dynamic tidycensus search for edge cases'
            }
        }
        
        output_path = self.config_dir / "pipeline_metadata.json"
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"   💾 Saved pipeline metadata: {output_path}")
    
    def _get_top_concepts(self, enriched_variables: Dict) -> List[Dict]:
        """Get statistics on top concepts."""
        
        concept_counts = defaultdict(int)
        for var_data in enriched_variables.values():
            concept = var_data.get('concept', 'Unknown')
            concept_counts[concept] += 1
        
        # Return top 10 concepts
        top_concepts = sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{'concept': concept, 'variable_count': count} for concept, count in top_concepts]
    
    def _print_pipeline_summary(self, all_variables: Dict, useful_variables: Dict, enriched_variables: Dict):
        """Print comprehensive build summary."""
        
        print("\n" + "="*80)
        print("🤖 AI-OPTIMIZED CENSUS SEMANTIC PIPELINE BUILD SUMMARY")
        print("="*80)
        
        print(f"📊 Variable Processing:")
        print(f"   Total Census variables fetched: {len(all_variables):,}")
        print(f"   Filtered to useful subset: {len(useful_variables):,} ({len(useful_variables)/len(all_variables)*100:.1f}%)")
        print(f"   Final enriched variables: {len(enriched_variables):,}")
        
        print(f"\n🎯 AI Optimization:")
        avg_keywords = sum(len(v.get('semantic_keywords', [])) for v in enriched_variables.values()) / len(enriched_variables)
        avg_aliases = sum(len(v.get('aliases', [])) for v in enriched_variables.values()) / len(enriched_variables)
        print(f"   Average keywords per variable: {avg_keywords:.1f}")
        print(f"   Average aliases per variable: {avg_aliases:.1f}")
        
        print(f"\n📁 Generated Files:")
        print(f"   📄 semantic_index.json - Complete enriched variable catalog")
        print(f"   🗄️  search_index.db - SQLite full-text search database")
        print(f"   📋 pipeline_metadata.json - Build statistics and metadata")
        
        print(f"\n⚡ Performance Profile:")
        print(f"   🚀 Designed for <50ms lookup times")
        print(f"   🎯 Covers majority of AI Census queries")
        print(f"   🔄 Annual refresh recommended")
        
        print(f"\n🐳 Container Ready:")
        print(f"   ✅ Pre-built indexes for fast runtime")
        print(f"   ✅ No API calls during query processing")
        print(f"   ✅ Self-contained semantic intelligence")
        
        print("="*80)
        print("🚀 AI-optimized Census pipeline ready for deployment!")
        print("="*80)

def main():
    """Build the AI-optimized Census semantic pipeline."""
    
    parser = argparse.ArgumentParser(description='Build AI-optimized Census semantic pipeline')
    parser.add_argument('--test-mode', action='store_true',
                       help='Run in test mode with limited variables')
    
    args = parser.parse_args()
    
    try:
        pipeline = CensusSemanticPipeline(test_mode=args.test_mode)
        
        # Note: Using asyncio for future async HTTP calls
        import asyncio
        asyncio.run(pipeline.build_complete_pipeline())
        
    except Exception as e:
        logger.error(f"Pipeline build failed: {e}")
        raise

if __name__ == "__main__":
    main()
