#!/usr/bin/env python3
"""
Pull all 28,152 ACS variables for spatial topology discovery
One API call, complete corpus, ready for intelligent analysis
"""

import requests
import json
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CensusVariablePuller:
    def __init__(self, base_path="../"):
        self.base_path = Path(base_path)
        self.variables_path = self.base_path / "complete_2023_acs_variables"
        self.variables_path.mkdir(parents=True, exist_ok=True)
        
        # Census API endpoints for variables
        self.endpoints = {
            'acs5': 'https://api.census.gov/data/2023/acs/acs5/variables.json',
            'acs1': 'https://api.census.gov/data/2023/acs/acs1/variables.json'
        }
        
        # Future expansion for SIPP/CPS
        self.future_endpoints = {
            'sipp': 'https://api.census.gov/data/2022/sipp/variables.json',
            'cps': 'https://api.census.gov/data/2023/cps/basic/variables.json'  # Census-hosted CPS
        }
    
    def pull_all_variables(self):
        """Pull complete variable corpus from Census API"""
        logger.info("🚀 Starting complete Census variable pull...")
        
        all_variables = {}
        total_count = 0
        
        for survey_type, endpoint in self.endpoints.items():
            logger.info(f"Pulling {survey_type} variables from {endpoint}")
            
            try:
                response = requests.get(endpoint)
                response.raise_for_status()
                
                data = response.json()
                variables = data.get('variables', {})
                
                logger.info(f"Retrieved {len(variables)} variables for {survey_type}")
                
                # Save raw JSON
                raw_file = self.variables_path / f"{survey_type}_variables_raw.json"
                with open(raw_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Process and structure
                processed_vars = self.process_variables(variables, survey_type)
                all_variables[survey_type] = processed_vars
                total_count += len(variables)
                
            except Exception as e:
                logger.error(f"Error pulling {survey_type}: {e}")
                continue
        
        logger.info(f"✅ COMPLETE: Retrieved {total_count} total variables across surveys")
        
        # Save complete corpus
        corpus_file = self.variables_path / "complete_census_corpus.json"
        with open(corpus_file, 'w') as f:
            json.dump(all_variables, f, indent=2)
        
        # Analyze structure immediately
        self.analyze_corpus_structure(all_variables)
        
        return all_variables
    
    def process_variables(self, variables, survey_type):
        """Process raw variables into structured format"""
        processed = []
        
        for var_id, var_data in variables.items():
            if var_id == 'for':  # Skip metadata entries
                continue
                
            processed_var = {
                'variable_id': var_id,
                'label': var_data.get('label', ''),
                'concept': var_data.get('concept', ''),
                'predicateType': var_data.get('predicateType', ''),
                'group': var_data.get('group', ''),
                'survey': survey_type,
                'retrieved': datetime.now().isoformat()
            }
            
            # Extract table family (B01, B02, etc.)
            if var_id.startswith(('B', 'C', 'S')):
                table_family = var_id[:3]
                processed_var['table_family'] = table_family
            
            # Classify complexity
            if 'total' in var_data.get('label', '').lower():
                processed_var['complexity'] = 'simple_count'
            elif 'percent' in var_data.get('label', '').lower() or 'rate' in var_data.get('label', '').lower():
                processed_var['complexity'] = 'calculated_rate'
            elif 'median' in var_data.get('label', '').lower():
                processed_var['complexity'] = 'statistical_measure'
            else:
                processed_var['complexity'] = 'unknown'
            
            processed.append(processed_var)
        
        return processed
    
    def analyze_corpus_structure(self, all_variables):
        """Analyze the complete corpus structure for intelligent chunking"""
        logger.info("🔍 Analyzing corpus structure...")
        
        analysis = {
            'total_variables': 0,
            'by_survey': {},
            'table_families': {},
            'complexity_distribution': {},
            'concept_domains': {}
        }
        
        all_vars_flat = []
        
        for survey, variables in all_variables.items():
            analysis['by_survey'][survey] = len(variables)
            analysis['total_variables'] += len(variables)
            all_vars_flat.extend(variables)
        
        # Analyze table families
        for var in all_vars_flat:
            family = var.get('table_family', 'unknown')
            if family not in analysis['table_families']:
                analysis['table_families'][family] = 0
            analysis['table_families'][family] += 1
            
            # Complexity distribution
            complexity = var.get('complexity', 'unknown')
            if complexity not in analysis['complexity_distribution']:
                analysis['complexity_distribution'][complexity] = 0
            analysis['complexity_distribution'][complexity] += 1
            
            # Concept domains (rough clustering)
            concept = var.get('concept', '').lower()
            if 'income' in concept or 'earnings' in concept:
                domain = 'economics'
            elif 'housing' in concept or 'rent' in concept:
                domain = 'housing'
            elif 'education' in concept or 'school' in concept:
                domain = 'education'
            elif 'employment' in concept or 'labor' in concept:
                domain = 'employment'
            elif 'race' in concept or 'ethnicity' in concept:
                domain = 'demographics'
            elif 'age' in concept or 'sex' in concept:
                domain = 'demographics'
            else:
                domain = 'other'
            
            if domain not in analysis['concept_domains']:
                analysis['concept_domains'][domain] = 0
            analysis['concept_domains'][domain] += 1
        
        # Save analysis
        analysis_file = self.variables_path / "corpus_structure_analysis.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        # Create DataFrame for easy exploration
        df = pd.DataFrame(all_vars_flat)
        df_file = self.variables_path / "complete_variables.csv"
        df.to_csv(df_file, index=False)
        
        logger.info(f"📊 Structure Analysis Complete:")
        logger.info(f"   Total Variables: {analysis['total_variables']}")
        logger.info(f"   Top Table Families: {sorted(analysis['table_families'].items(), key=lambda x: x[1], reverse=True)[:10]}")
        logger.info(f"   Complexity: {analysis['complexity_distribution']}")
        logger.info(f"   Domains: {analysis['concept_domains']}")
        
        return analysis, df
    
    def select_intelligent_sample(self, sample_size=1000):
        """Select representative sample across domains and complexity"""
        logger.info(f"🎯 Selecting intelligent {sample_size} variable sample...")
        
        # Load complete corpus
        df_file = self.variables_path / "complete_variables.csv"
        if not df_file.exists():
            logger.error("Complete corpus not found. Run pull_all_variables() first.")
            return None
        
        df = pd.read_csv(df_file)
        
        # Stratified sampling strategy
        sample_strategy = {
            'table_families': 0.4,  # 40% - representative across table families
            'complexity': 0.3,      # 30% - across complexity levels
            'concepts': 0.2,        # 20% - across concept domains
            'random': 0.1           # 10% - pure random for unbiased discovery
        }
        
        selected_samples = []
        
        # Sample by table families
        family_sample_size = int(sample_size * sample_strategy['table_families'])
        top_families = df['table_family'].value_counts().head(20).index
        family_sample = df[df['table_family'].isin(top_families)].sample(
            n=min(family_sample_size, len(df[df['table_family'].isin(top_families)])),
            random_state=42
        )
        selected_samples.append(family_sample)
        
        # Sample by complexity
        complexity_sample_size = int(sample_size * sample_strategy['complexity'])
        remaining_df = df[~df.index.isin(family_sample.index)]
        complexity_sample = remaining_df.groupby('complexity').apply(
            lambda x: x.sample(n=min(complexity_sample_size//4, len(x)), random_state=42)
        ).reset_index(drop=True)
        selected_samples.append(complexity_sample)
        
        # Random sample from remainder
        random_sample_size = sample_size - sum(len(s) for s in selected_samples)
        remaining_df = df[~df.index.isin(pd.concat(selected_samples).index)]
        if len(remaining_df) > 0:
            random_sample = remaining_df.sample(
                n=min(random_sample_size, len(remaining_df)),
                random_state=42
            )
            selected_samples.append(random_sample)
        
        # Combine samples
        final_sample = pd.concat(selected_samples).drop_duplicates()
        
        # Save intelligent sample
        sample_file = self.variables_path / f"intelligent_sample_{len(final_sample)}.csv"
        final_sample.to_csv(sample_file, index=False)
        
        sample_vars_file = self.variables_path / f"intelligent_sample_{len(final_sample)}_variables.json"
        sample_vars = final_sample['variable_id'].tolist()
        with open(sample_vars_file, 'w') as f:
            json.dump(sample_vars, f, indent=2)
        
        logger.info(f"✅ Intelligent sample selected: {len(final_sample)} variables")
        logger.info(f"   Sample composition:")
        logger.info(f"   - Table families: {final_sample['table_family'].value_counts().head(10).to_dict()}")
        logger.info(f"   - Complexity: {final_sample['complexity'].value_counts().to_dict()}")
        
        return final_sample

def main():
    """Execute the complete variable pull and analysis"""
    puller = CensusVariablePuller()
    
    # Step 1: Pull everything (one API call, ~5MB)
    logger.info("🚀 STEP 1: Pulling complete Census variable corpus...")
    all_variables = puller.pull_all_variables()
    
    # Step 2: Analyze structure
    logger.info("🔍 STEP 2: Complete corpus structure analysis done during pull")
    
    # Step 3: Select intelligent sample for cost discovery
    logger.info("🎯 STEP 3: Selecting intelligent sample for enrichment testing...")
    sample = puller.select_intelligent_sample(1000)
    
    logger.info("✅ READY FOR SPATIAL TOPOLOGY DISCOVERY")
    logger.info("   Next steps:")
    logger.info("   1. Load intelligent sample for collaborative enrichment")
    logger.info("   2. Generate embeddings and test clustering")
    logger.info("   3. Validate topology emergence")
    logger.info("   4. Scale to full 28K if successful")

if __name__ == "__main__":
    main()
